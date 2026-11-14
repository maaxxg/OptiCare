import json
import logging

import httpx
import pytest

from app.adapters import factories
from app.adapters.llm_api import OpenAICompatibleLLMClient
from app.adapters.routing_ors import MAX_MATRIX_ROUTES, OrsRoutingClient
from app.adapters.types import AdapterError, LatLon
from app.config import Settings


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _llm(handler, key="sekret-kljuc") -> OpenAICompatibleLLMClient:
    return OpenAICompatibleLLMClient(
        "https://llm.test/v1/", "test-model", key, client=_client(handler)
    )


def test_llm_request_shape_and_content():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers.get("authorization")
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"a": 1}'}}]})

    assert _llm(handler).complete("sys", "usr") == '{"a": 1}'
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sekret-kljuc"
    body = seen["body"]
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


def test_llm_no_auth_header_without_key():
    def handler(req: httpx.Request) -> httpx.Response:
        assert "authorization" not in req.headers
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    assert _llm(handler, key="").complete("s", "u") == "{}"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="tajni odgovor"),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, text="not json"),
    ],
)
def test_llm_errors_raise_adapter_error(response):
    with pytest.raises(AdapterError) as exc:
        _llm(lambda req: response).complete("s", "u")
    assert "tajni odgovor" not in str(exc.value)


def test_llm_timeout_raises_adapter_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(AdapterError):
        _llm(handler).complete("s", "u")


def test_llm_never_logs_prompt_response_or_key(caplog):
    prompt = "Pacijent MBO 123456789 treba prijevoz"
    answer = "ODGOVOR-MODELA-XYZ"

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": answer}}]})

    with caplog.at_level(logging.DEBUG):
        _llm(handler).complete("sys", prompt)
        with pytest.raises(AdapterError):
            _llm(lambda r: httpx.Response(500, text=answer)).complete("sys", prompt)
    assert caplog.records
    text = caplog.text
    for secret in ("123456789", prompt, answer, "sekret-kljuc"):
        assert secret not in text


def _ors(handler) -> OrsRoutingClient:
    return OrsRoutingClient("ors-key", "https://ors.test", client=_client(handler))


PTS = [LatLon(lat=44.5, lon=15.1), LatLon(lat=44.6, lon=15.3)]


def test_ors_sends_lon_lat_and_parses_matrix():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "durations": [[0, 60.5], [70, 0]],
                "distances": [[0, 1000], [1200, 0]],
            },
        )

    m = _ors(handler).matrix(PTS)
    assert seen["url"] == "https://ors.test/v2/matrix/driving-car"
    assert seen["auth"] == "ors-key"
    assert seen["body"]["locations"] == [[15.1, 44.5], [15.3, 44.6]]
    assert seen["body"]["metrics"] == ["duration", "distance"]
    assert m.durations_s == [[0.0, 60.5], [70.0, 0.0]]
    assert m.distances_m == [[0.0, 1000.0], [1200.0, 0.0]]


def test_ors_null_cell_raises_with_indices():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"durations": [[0, None], [1, 0]], "distances": [[0, 1], [1, 0]]}
        )

    with pytest.raises(AdapterError, match="0 and 1"):
        _ors(handler).matrix(PTS)


def test_ors_http_error_raises():
    with pytest.raises(AdapterError):
        _ors(lambda r: httpx.Response(403)).matrix(PTS)


def test_ors_oversize_rejected_without_http_call():
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("must not call")

    n = int(MAX_MATRIX_ROUTES**0.5) + 1
    with pytest.raises(AdapterError):
        _ors(handler).matrix([LatLon(lat=44.5, lon=15.1)] * n)


def _settings(monkeypatch, **kw):
    s = Settings(_env_file=None, **kw)
    monkeypatch.setattr(factories, "get_settings", lambda: s)


def test_factory_api_llm_requires_config(monkeypatch):
    _settings(monkeypatch, llm_backend="api")
    with pytest.raises(ValueError, match="LLM_BASE_URL"):
        factories.get_llm_client()
    _settings(monkeypatch, llm_backend="api", llm_base_url="https://x/v1", llm_model="m")
    assert isinstance(factories.get_llm_client(), OpenAICompatibleLLMClient)


def test_factory_ors_requires_key(monkeypatch):
    _settings(monkeypatch, routing_backend="ors")
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        factories.get_routing_client()
    _settings(monkeypatch, routing_backend="ors", ors_api_key="k")
    assert isinstance(factories.get_routing_client(), OrsRoutingClient)


def test_routing_client_is_reused(monkeypatch):
    factories._ors_routing_client.cache_clear()
    _settings(monkeypatch, routing_backend="ors", ors_api_key="k")
    assert factories.get_routing_client() is factories.get_routing_client()
    factories._ors_routing_client.cache_clear()


def test_check_routing_config(monkeypatch):
    from app.main import StartupCheckError, check_routing_config

    _settings(monkeypatch, routing_backend="ors")
    with pytest.raises(StartupCheckError, match="Routing adapter"):
        check_routing_config()
    _settings(monkeypatch, routing_backend="mock")
    check_routing_config()
