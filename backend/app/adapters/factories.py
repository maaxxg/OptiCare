from functools import lru_cache

from app.adapters.geocoding import GeocodingClient, MockGeocodingClient
from app.adapters.llm import LLMClient, MockLLMClient
from app.adapters.llm_api import OpenAICompatibleLLMClient
from app.adapters.routing import MockRoutingClient, RoutingClient
from app.adapters.routing_ors import OrsRoutingClient
from app.adapters.sms import MockSmsClient, SmsClient
from app.config import get_settings


def _not_implemented(kind: str, backend: str) -> NotImplementedError:
    return NotImplementedError(f"{kind} backend '{backend}' is not implemented yet")


def get_llm_client() -> LLMClient:
    settings = get_settings()
    backend = settings.llm_backend
    if backend == "mock":
        return MockLLMClient()
    if backend == "api":
        if not settings.llm_base_url or not settings.llm_model:
            raise ValueError("LLM_BACKEND=api requires LLM_BASE_URL and LLM_MODEL to be set")
        return OpenAICompatibleLLMClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout_s=settings.llm_timeout_s,
        )
    raise _not_implemented("LLM", backend)


def get_routing_client() -> RoutingClient:
    settings = get_settings()
    backend = settings.routing_backend
    if backend == "mock":
        return MockRoutingClient()
    if backend == "ors":
        key = settings.ors_api_key.get_secret_value()
        if not key:
            raise ValueError("ROUTING_BACKEND=ors requires ORS_API_KEY to be set")
        return OrsRoutingClient(
            api_key=key, base_url=settings.ors_base_url, timeout_s=settings.ors_timeout_s
        )
    raise _not_implemented("Routing", backend)


def get_geocoding_client() -> GeocodingClient:
    backend = get_settings().geocoding_backend
    if backend == "mock":
        return MockGeocodingClient()
    raise _not_implemented("Geocoding", backend)


@lru_cache
def _mock_sms_client() -> MockSmsClient:
    return MockSmsClient()


def get_sms_client() -> SmsClient:
    # The mock is a process-wide singleton so its outbox survives across requests.
    backend = get_settings().sms_backend
    if backend == "mock":
        return _mock_sms_client()
    raise _not_implemented("SMS", backend)
