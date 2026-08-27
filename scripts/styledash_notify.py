"""Best-effort private owner notifications for StyleDash."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
from typing import Iterable
from urllib.request import Request, urlopen


LOGGER = logging.getLogger("styledash.notify")

_NOTIFICATION_QUEUE_LIMIT = 128


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def mask_email(email: str) -> str:
    """Return a notification-safe masked email address."""
    value = (email or "").strip()

    if "@" not in value:
        return "***"

    local, domain = value.split("@", 1)

    if not local:
        return "***@" + domain

    visible = local[:2]
    hidden = "*" * max(4, len(local) - len(visible))

    return f"{visible}{hidden}@{domain}"


def mask_phone(phone: str) -> str:
    """Return a notification-safe masked phone number, e.g. '+91 98******10'."""
    value = (phone or "").strip()
    match = re.match(r"^(\+\d{1,3})(\d{5,})$", value)
    if not match:
        return "***"
    country, national = match.groups()
    if len(national) <= 4:
        return f"{country} {'*' * len(national)}"
    visible_start = national[:2]
    visible_end = national[-2:]
    hidden = "*" * (len(national) - 4)
    return f"{country} {visible_start}{hidden}{visible_end}"


class NtfyNotifier:
    """Failure-isolated ntfy publisher."""

    def __init__(
        self,
        *,
        enabled: bool,
        base_url: str,
        topic: str,
        timeout: float = 2.5,
        background: bool = False,
    ) -> None:
        self.enabled = bool(enabled)
        self.base_url = (base_url or "").strip().rstrip("/")
        self.topic = (topic or "").strip()
        self.timeout = min(max(float(timeout), 0.5), 3.0)
        self.background = bool(background)

    @classmethod
    def from_environment(cls) -> "NtfyNotifier":
        return cls(
            enabled=_enabled(
                os.environ.get("STYLEDASH_NTFY_ENABLED")
            ),
            base_url=os.environ.get(
                "STYLEDASH_NTFY_BASE_URL",
                "https://ntfy.sh",
            ),
            topic=os.environ.get(
                "STYLEDASH_NTFY_TOPIC",
                "",
            ),
            background=_enabled(
                os.environ.get(
                    "STYLEDASH_NTFY_BACKGROUND"
                )
            ),
        )

    @property
    def configured(self) -> bool:
        return (
            self.enabled
            and self.base_url.startswith(
                ("https://", "http://")
            )
            and bool(self.topic)
        )

    def _deliver(
        self,
        *,
        safe_event: str,
        payload: dict,
    ) -> bool:
        try:
            request = Request(
                self.base_url,
                data=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
                headers={
                    "Content-Type":
                        "application/json; charset=utf-8",
                    "User-Agent":
                        "Vibe4You-Owner-Notifications/1.0",
                },
                method="POST",
            )

            with urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                status = getattr(
                    response,
                    "status",
                    200,
                )

                if not 200 <= int(status) < 300:
                    LOGGER.warning(
                        "Vibe4You notification delivery "
                        "failed event=%s",
                        safe_event,
                    )
                    return False

            return True

        except Exception:
            # Never expose topic, URL, credentials,
            # customer data or payment data.
            LOGGER.warning(
                "Vibe4You notification delivery "
                "failed event=%s",
                safe_event,
            )
            return False

    def send(
        self,
        *,
        event: str,
        title: str,
        message: str,
        priority: int = 5,
        tags: Iterable[str] | None = None,
    ) -> bool:
        """
        Publish or enqueue one owner notification.

        When background mode is enabled, the calling business
        operation never waits for the ntfy network request.
        """
        safe_event = str(
            event or "unknown"
        )[:80]

        if not self.configured:
            return False

        payload = {
            "topic": self.topic,
            "title": str(title)[:250],
            "message": str(message)[:4000],
            "priority": max(
                1,
                min(int(priority), 5),
            ),
            "tags": [
                str(tag)[:100]
                for tag in (tags or [])
                if str(tag).strip()
            ][:10],
        }

        if self.background:
            return _DISPATCHER.submit(
                self,
                safe_event,
                payload,
            )

        return self._deliver(
            safe_event=safe_event,
            payload=payload,
        )


class _NotificationDispatcher:
    """Bounded single-worker dispatcher for owner alerts."""

    def __init__(
        self,
        max_queue: int,
    ) -> None:
        self._queue = queue.Queue(
            maxsize=max_queue
        )
        self._worker_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if (
                self._worker is not None
                and self._worker.is_alive()
            ):
                return

            self._worker = threading.Thread(
                target=self._run,
                name="styledash-ntfy",
                daemon=True,
            )
            self._worker.start()

    def submit(
        self,
        notifier: NtfyNotifier,
        safe_event: str,
        payload: dict,
    ) -> bool:
        self._ensure_worker()

        try:
            self._queue.put_nowait(
                (
                    notifier,
                    safe_event,
                    payload,
                )
            )
            return True

        except queue.Full:
            # Never block an order/payment/request because
            # the notification queue is saturated.
            LOGGER.warning(
                "Vibe4You notification queue full "
                "event=%s",
                safe_event,
            )
            return False

    def _run(self) -> None:
        while True:
            (
                notifier,
                safe_event,
                payload,
            ) = self._queue.get()

            try:
                notifier._deliver(
                    safe_event=safe_event,
                    payload=payload,
                )
            except Exception:
                # _deliver already isolates normal failures,
                # but the worker itself must never die.
                LOGGER.warning(
                    "Vibe4You notification worker "
                    "failed event=%s",
                    safe_event,
                )
            finally:
                self._queue.task_done()

    def wait(
        self,
        timeout: float = 5.0,
    ) -> bool:
        """
        Wait for queued notifications.

        Intended for diagnostics/tests, not request handling.
        """
        deadline = (
            time.monotonic()
            + max(float(timeout), 0.0)
        )

        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = (
                    deadline - time.monotonic()
                )

                if remaining <= 0:
                    return False

                self._queue.all_tasks_done.wait(
                    remaining
                )

        return True


_DISPATCHER = _NotificationDispatcher(
    _NOTIFICATION_QUEUE_LIMIT
)


def wait_for_notifications(
    timeout: float = 5.0,
) -> bool:
    return _DISPATCHER.wait(timeout)


def owner_notifier() -> NtfyNotifier:
    return NtfyNotifier.from_environment()
