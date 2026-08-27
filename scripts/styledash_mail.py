"""Private SMTP delivery for StyleDash customer password-reset messages.

This module intentionally accepts configuration only from the server runtime.
It never logs configuration values or reset tokens, and its SMTP transport is
injectable so tests do not need a real provider.
"""

from __future__ import annotations

import os
import queue
import smtplib
import ssl
import threading
from email.message import EmailMessage
from typing import Callable, Mapping, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit


SMTP_REQUIRED_VARIABLES = (
    "STYLEDASH_SMTP_HOST",
    "STYLEDASH_SMTP_PORT",
    "STYLEDASH_SMTP_USERNAME",
    "STYLEDASH_SMTP_PASSWORD",
    "STYLEDASH_PASSWORD_RESET_FROM",
    "STYLEDASH_PASSWORD_RESET_URL",
)
SMTP_TIMEOUT_SECONDS = 10


class SmtpConfigurationError(ValueError):
    """Raised without configuration values when the private mail config is invalid."""


class SmtpConnection(Protocol):
    def ehlo(self) -> object: ...

    def starttls(self, *, context: ssl.SSLContext) -> object: ...

    def login(self, user: str, password: str) -> object: ...

    def send_message(self, message: EmailMessage) -> object: ...

    def quit(self) -> object: ...


SmtpFactory = Callable[..., SmtpConnection]
PasswordResetFailure = Callable[[], None]
TransactionalMessageSender = Callable[[str, str, str], None]


def _required_value(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "")
    if not isinstance(value, str) or not value:
        raise SmtpConfigurationError("Password-reset SMTP configuration is incomplete")
    return value


def _contains_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _validate_host(value: str) -> str:
    if len(value) > 253 or _contains_control_characters(value) or any(character.isspace() for character in value):
        raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
    return value


def _validate_email(value: str) -> str:
    if len(value) > 254 or _contains_control_characters(value) or value.count("@") != 1:
        raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
    local, domain = value.rsplit("@", 1)
    if not local or not domain or any(character.isspace() for character in value):
        raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
    return value


def _validate_reset_url(value: str) -> str:
    if _contains_control_characters(value):
        raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.fragment:
        raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
    return value


class SmtpPasswordResetSender:
    """TLS-only SMTP sender; credentials and tokens are never logged."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        reset_url: str,
        *,
        smtp_factory: SmtpFactory = smtplib.SMTP,
    ) -> None:
        self.host = _validate_host(host)
        if not 1 <= port <= 65535:
            raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
        if _contains_control_characters(username) or _contains_control_characters(password):
            raise SmtpConfigurationError("Password-reset SMTP configuration is invalid")
        self.port = port
        self.username = username
        self.password = password
        self.from_address = _validate_email(from_address)
        self.reset_url = _validate_reset_url(reset_url)
        self.smtp_factory = smtp_factory

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        smtp_factory: SmtpFactory = smtplib.SMTP,
    ) -> "SmtpPasswordResetSender | None":
        values = os.environ if environ is None else environ
        configured = [name for name in SMTP_REQUIRED_VARIABLES if values.get(name)]
        if not configured:
            return None
        if len(configured) != len(SMTP_REQUIRED_VARIABLES):
            raise SmtpConfigurationError("Password-reset SMTP configuration is incomplete")
        try:
            port = int(_required_value(values, "STYLEDASH_SMTP_PORT"), 10)
        except ValueError as exc:
            raise SmtpConfigurationError("Password-reset SMTP configuration is invalid") from exc
        return cls(
            _required_value(values, "STYLEDASH_SMTP_HOST"),
            port,
            _required_value(values, "STYLEDASH_SMTP_USERNAME"),
            _required_value(values, "STYLEDASH_SMTP_PASSWORD"),
            _required_value(values, "STYLEDASH_PASSWORD_RESET_FROM"),
            _required_value(values, "STYLEDASH_PASSWORD_RESET_URL"),
            smtp_factory=smtp_factory,
        )

    def _reset_link(self, token: str) -> str:
        parsed = urlsplit(self.reset_url)
        # URL fragments are not transmitted in HTTP requests, so the raw
        # token cannot enter server/tunnel access logs or Referer headers.
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, urlencode({"token": token})))

    def _send_message(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = _validate_email(recipient)
        message["Subject"] = subject
        message.set_content(body)
        client = self.smtp_factory(self.host, self.port, timeout=SMTP_TIMEOUT_SECONDS)
        try:
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            client.login(self.username, self.password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except Exception:
                pass

    def __call__(self, recipient: str, token: str) -> None:
        self._send_message(
            recipient,
            "Reset your Vibe4You password",
            "A password reset was requested for your Vibe4You account.\n\n"
            f"Reset your password: {self._reset_link(token)}\n\n"
            "This link expires in 30 minutes and can be used once. If you did not request it, you can ignore this email.",
        )

    def send_transactional(self, recipient: str, subject: str, body: str) -> None:
        self._send_message(recipient, subject, body)


class PasswordResetDeliveryQueue:
    """Bounded, drainable in-memory password-reset delivery worker.

    Tokens are held only in process memory until delivery completes. `close()`
    drains queued work so each send either completes or runs its failure
    callback before a controlled server shutdown finishes.
    """

    def __init__(self, sender: Callable[[str, str], None], *, max_pending: int = 100) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._sender = sender
        self._queue: queue.Queue[tuple[str, str, PasswordResetFailure] | object] = queue.Queue(maxsize=max_pending)
        self._stop = object()
        self._lock = threading.Lock()
        self._closed = False
        self._worker = threading.Thread(target=self._run, name="styledash-password-reset-mail", daemon=True)
        self._worker.start()

    def dispatch(self, recipient: str, token: str, on_failure: PasswordResetFailure) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Password-reset delivery is unavailable")
            try:
                self._queue.put_nowait((recipient, token, on_failure))
            except queue.Full as exc:
                raise RuntimeError("Password-reset delivery is unavailable") from exc

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._stop:
                    return
                recipient, token, on_failure = item
                try:
                    self._sender(recipient, token)
                except Exception:
                    try:
                        on_failure()
                    except Exception:
                        pass
            finally:
                self._queue.task_done()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._queue.put(self._stop)
        self._worker.join()


class TransactionalDeliveryQueue:
    """Bounded, failure-isolated queue for transactional customer messages."""

    def __init__(self, sender: TransactionalMessageSender, *, max_pending: int = 100) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._sender = sender
        self._queue: queue.Queue[tuple[str, str, str] | object] = queue.Queue(maxsize=max_pending)
        self._stop = object()
        self._lock = threading.Lock()
        self._closed = False
        self._worker = threading.Thread(
            target=self._run, name="styledash-transactional-mail", daemon=True
        )
        self._worker.start()

    def dispatch(self, recipient: str, subject: str, body: str) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Transactional delivery is unavailable")
            try:
                self._queue.put_nowait((recipient, subject, body))
            except queue.Full as exc:
                raise RuntimeError("Transactional delivery is unavailable") from exc

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is self._stop:
                    return
                recipient, subject, body = item
                try:
                    self._sender(recipient, subject, body)
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._queue.put(self._stop)
        self._worker.join()
