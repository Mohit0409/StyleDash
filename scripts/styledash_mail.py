"""Private SMTP delivery for StyleDash customer password-reset messages.

This module intentionally accepts configuration only from the server runtime.
It never logs configuration values or reset tokens, and its SMTP transport is
injectable so tests do not need a real provider.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Callable, Mapping, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
        query = parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("token", token))
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))

    def __call__(self, recipient: str, token: str) -> None:
        message = EmailMessage()
        message["From"] = self.from_address
        message["To"] = _validate_email(recipient)
        message["Subject"] = "Reset your Style Dash password"
        message.set_content(
            "A password reset was requested for your Style Dash account.\n\n"
            f"Reset your password: {self._reset_link(token)}\n\n"
            "This link expires in 30 minutes and can be used once. If you did not request it, you can ignore this email."
        )
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
