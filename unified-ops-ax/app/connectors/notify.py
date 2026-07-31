"""Notifier adapters (port pattern) — the delivery channel for HITL-approved
follow-ups. The agent never calls these directly; only `approve_and_send`
(the human gate) does. Fake = in-memory outbox (offline/test); SMTP via stdlib;
Twilio SMS via httpx (MockTransport-testable)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.config import get_settings


@dataclass
class SendResult:
    message_id: str
    channel: str
    status: str = "sent"


class NotifierPort(Protocol):
    name: str

    def send(self, *, to: str, body: str, subject: str | None = None, channel: str = "email") -> SendResult:
        ...


@dataclass
class FakeNotifier:
    name: str = "fake"
    outbox: list = field(default_factory=list)
    _seq: int = 0

    def send(self, *, to, body, subject=None, channel="email") -> SendResult:
        self._seq += 1
        mid = f"FAKE-MSG-{self._seq:04d}"
        self.outbox.append({"id": mid, "to": to, "subject": subject, "body": body, "channel": channel})
        return SendResult(message_id=mid, channel=channel)

    def clear(self) -> None:
        self.outbox.clear()
        self._seq = 0


class ConsoleNotifier:
    name = "console"

    def send(self, *, to, body, subject=None, channel="email") -> SendResult:
        print(f"[notify:{channel}] to={to} subject={subject!r} body={body[:120]!r}")
        return SendResult(message_id="console", channel=channel)


class SmtpNotifier:  # pragma: no cover - needs a live SMTP server
    """Real email via stdlib smtplib (no extra dependency)."""
    name = "smtp"

    def __init__(self, host, port, user, password, sender) -> None:
        self._host, self._port, self._user, self._password, self._from = host, port, user, password, sender

    def send(self, *, to, body, subject=None, channel="email") -> SendResult:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self._from or self._user
        msg["To"] = to
        msg["Subject"] = subject or "(no subject)"
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port) as smtp:
            smtp.starttls()
            if self._user:
                smtp.login(self._user, self._password)
            smtp.send_message(msg)
        return SendResult(message_id=msg["Message-ID"] or "smtp", channel="email")


class TwilioNotifier:
    """Real SMS via the Twilio Messages API. httpx client is injectable so the
    request shape is testable offline via MockTransport."""
    name = "twilio"

    def __init__(self, account_sid, auth_token, from_number, http=None) -> None:
        import httpx

        self._http = http or httpx.Client(timeout=30)
        self._sid = account_sid
        self._token = auth_token
        self._from = from_number

    def send(self, *, to, body, subject=None, channel="sms") -> SendResult:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self._sid}/Messages.json"
        resp = self._http.post(url, auth=(self._sid, self._token),
                               data={"To": to, "From": self._from, "Body": body})
        resp.raise_for_status()
        data = resp.json()
        return SendResult(message_id=str(data.get("sid", "")), channel="sms",
                          status=data.get("status", "queued"))


_FAKE_SINGLETON = FakeNotifier()


def build_notifier() -> NotifierPort:
    s = get_settings()
    p = s.notifier_provider
    if p == "fake":
        return _FAKE_SINGLETON
    if p == "console":
        return ConsoleNotifier()
    if p == "smtp":
        return SmtpNotifier(s.smtp_host, s.smtp_port, s.smtp_user, s.smtp_password, s.smtp_from)
    if p == "twilio":
        if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number):
            raise ValueError("missing TWILIO_* settings")
        return TwilioNotifier(s.twilio_account_sid, s.twilio_auth_token, s.twilio_from_number)
    raise ValueError(f"unknown notifier provider: {p}")
