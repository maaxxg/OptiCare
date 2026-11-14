from collections.abc import Callable
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the raw model text (expected JSON). Validation is the caller's job.

        Implementations must not log prompt or response content.
        """
        ...


class MockLLMClient:
    """Returns a fixed `response`, or `responder(system, user)` when given."""

    def __init__(
        self,
        response: str = "{}",
        responder: Callable[[str, str], str] | None = None,
    ) -> None:
        self.response = response
        self.responder = responder

    def complete(self, system: str, user: str) -> str:
        if self.responder is not None:
            return self.responder(system, user)
        return self.response
