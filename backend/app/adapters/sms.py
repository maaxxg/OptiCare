import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class SmsClient(Protocol):
    def send(self, to: str, text: str) -> str:
        """Send a message and return its id."""
        ...


@dataclass(frozen=True)
class SentSms:
    id: str
    to: str
    text: str
    sent_at: datetime


class MockSmsClient:
    def __init__(self) -> None:
        self.outbox: list[SentSms] = []

    def send(self, to: str, text: str) -> str:
        message_id = f"mock-{uuid.uuid4().hex[:12]}"
        self.outbox.append(SentSms(message_id, to, text, datetime.now(ZoneInfo("Europe/Zagreb"))))
        # Never log the phone number or the text.
        logger.info("Mock SMS %s queued (%d chars)", message_id, len(text))
        return message_id
