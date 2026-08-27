from __future__ import annotations

import importlib.util
import unittest
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("styledash_mail", ROOT / "scripts" / "styledash_mail.py")
assert SPEC and SPEC.loader
MAIL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAIL)


class FakeSmtp:
    def __init__(self, host: str, port: int, *, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.ehlo_calls = 0
        self.tls_context = None
        self.login_values = None
        self.messages: list[EmailMessage] = []
        self.quit_called = False

    def ehlo(self) -> None:
        self.ehlo_calls += 1

    def starttls(self, *, context) -> None:
        self.tls_context = context

    def login(self, user: str, password: str) -> None:
        self.login_values = (user, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)

    def quit(self) -> None:
        self.quit_called = True


class SmtpPasswordResetSenderTests(unittest.TestCase):
    def configuration(self) -> dict[str, str]:
        return {
            "STYLEDASH_SMTP_HOST": "smtp.example.test",
            "STYLEDASH_SMTP_PORT": "587",
            "STYLEDASH_SMTP_USERNAME": "mailer@example.test",
            "STYLEDASH_SMTP_PASSWORD": "not-a-real-test-secret",
            "STYLEDASH_PASSWORD_RESET_FROM": "mailer@example.test",
            "STYLEDASH_PASSWORD_RESET_URL": "https://styledash.example.test/reset-password?source=email",
        }

    def test_missing_or_partial_private_configuration_fails_closed(self) -> None:
        self.assertIsNone(MAIL.SmtpPasswordResetSender.from_environment({}))
        partial = self.configuration()
        partial.pop("STYLEDASH_SMTP_PASSWORD")
        with self.assertRaises(MAIL.SmtpConfigurationError):
            MAIL.SmtpPasswordResetSender.from_environment(partial)

    def test_sender_uses_authenticated_starttls_and_keeps_token_out_of_headers(self) -> None:
        connections: list[FakeSmtp] = []

        def smtp_factory(*args, **kwargs) -> FakeSmtp:
            connection = FakeSmtp(*args, **kwargs)
            connections.append(connection)
            return connection

        sender = MAIL.SmtpPasswordResetSender.from_environment(
            self.configuration(), smtp_factory=smtp_factory
        )
        assert sender is not None
        token = "test-reset-token-only-in-message-body"
        sender("customer@example.test", token)

        self.assertEqual(len(connections), 1)
        connection = connections[0]
        self.assertEqual((connection.host, connection.port, connection.timeout), ("smtp.example.test", 587, MAIL.SMTP_TIMEOUT_SECONDS))
        self.assertEqual(connection.ehlo_calls, 2)
        self.assertIsNotNone(connection.tls_context)
        self.assertEqual(connection.login_values, ("mailer@example.test", "not-a-real-test-secret"))
        self.assertTrue(connection.quit_called)
        self.assertEqual(len(connection.messages), 1)
        message = connection.messages[0]
        self.assertEqual(message["To"], "customer@example.test")
        self.assertNotIn(token, message["From"])
        self.assertNotIn(token, message["To"])
        self.assertNotIn(token, message["Subject"])
        self.assertIn(token, message.get_content())
        link = next(line.removeprefix("Reset your password: ") for line in message.get_content().splitlines() if line.startswith("Reset your password: "))
        parsed = urlsplit(link)
        self.assertEqual(parsed.query, "source=email")
        self.assertEqual(parse_qs(parsed.fragment), {"token": [token]})

    def test_sender_rejects_insecure_or_header_injection_configuration(self) -> None:
        insecure = self.configuration()
        insecure["STYLEDASH_PASSWORD_RESET_URL"] = "http://styledash.example.test/reset-password"
        with self.assertRaises(MAIL.SmtpConfigurationError):
            MAIL.SmtpPasswordResetSender.from_environment(insecure)
        injected = self.configuration()
        injected["STYLEDASH_PASSWORD_RESET_FROM"] = "mailer@example.test\r\nBcc: victim@example.test"
        with self.assertRaises(MAIL.SmtpConfigurationError):
            MAIL.SmtpPasswordResetSender.from_environment(injected)

    def test_transactional_sender_reuses_authenticated_tls_transport(self) -> None:
        connections: list[FakeSmtp] = []

        def smtp_factory(*args, **kwargs) -> FakeSmtp:
            connection = FakeSmtp(*args, **kwargs)
            connections.append(connection)
            return connection

        sender = MAIL.SmtpPasswordResetSender.from_environment(
            self.configuration(), smtp_factory=smtp_factory
        )
        assert sender is not None
        sender.send_transactional(
            "customer@example.test",
            "Your Vibe4You order update",
            "Order SD-TEST from Test Shop is now Shipped.",
        )
        self.assertEqual(len(connections), 1)
        message = connections[0].messages[0]
        self.assertEqual(message["To"], "customer@example.test")
        self.assertEqual(message["Subject"], "Your Vibe4You order update")
        self.assertIn("Test Shop is now Shipped", message.get_content())
        self.assertEqual(connections[0].login_values, ("mailer@example.test", "not-a-real-test-secret"))
        self.assertIsNotNone(connections[0].tls_context)

    def test_transactional_queue_drains_and_isolates_sender_failure(self) -> None:
        attempts = []

        def failing_sender(recipient: str, subject: str, body: str) -> None:
            attempts.append((recipient, subject, body))
            raise RuntimeError("simulated delivery failure")

        delivery_queue = MAIL.TransactionalDeliveryQueue(failing_sender, max_pending=1)
        delivery_queue.dispatch("customer@example.test", "Order update", "Shipped")
        delivery_queue.close()
        self.assertEqual(attempts, [("customer@example.test", "Order update", "Shipped")])
        with self.assertRaises(RuntimeError):
            delivery_queue.dispatch("customer@example.test", "After close", "ignored")

    def test_delivery_queue_is_bounded_and_drains_for_deterministic_shutdown(self) -> None:
        deliveries = []
        failures = []
        delivery_queue = MAIL.PasswordResetDeliveryQueue(
            lambda email, token: deliveries.append((email, token)), max_pending=1
        )
        delivery_queue.dispatch("customer@example.test", "first-test-token", lambda: failures.append("first"))
        delivery_queue.close()
        self.assertEqual(deliveries, [("customer@example.test", "first-test-token")])
        self.assertEqual(failures, [])
        with self.assertRaises(RuntimeError):
            delivery_queue.dispatch("customer@example.test", "after-close-token", lambda: failures.append("after-close"))


if __name__ == "__main__":
    unittest.main()
