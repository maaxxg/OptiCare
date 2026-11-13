from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Return the raw model text (expected JSON). Validation is the caller's job.

        Implementations must not log prompt or response content.
        """
        ...


class MockLLMClient:
    def __init__(self, response: str = "{}") -> None:
        self.response = response

    def complete(self, system: str, user: str) -> str:
        return self.response
