import logging
import time

import httpx

from app.adapters.types import AdapterError

logger = logging.getLogger(__name__)


class OpenAICompatibleLLMClient:
    """Generic OpenAI-compatible chat client, configured only through settings.

    Never logs prompt, response or key: only model, HTTP status and latency.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_s: float = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx.Client(timeout=timeout_s)

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        start = time.monotonic()
        try:
            resp = self._client.post(self._url, json=body, headers=self._headers)
        except httpx.HTTPError as exc:
            raise AdapterError(f"LLM request failed: {type(exc).__name__}") from None
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "LLM call model=%s status=%s latency_ms=%s", self._model, resp.status_code, latency_ms
        )
        if resp.status_code != 200:
            raise AdapterError(f"LLM returned HTTP {resp.status_code}")
        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise AdapterError("LLM response is malformed") from None
        if not isinstance(content, str):
            raise AdapterError("LLM response is malformed")
        return content
