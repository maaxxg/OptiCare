import logging

from app.adapters import (
    get_geocoding_client,
    get_llm_client,
    get_routing_client,
    get_sms_client,
)
from app.adapters.geocoding import MockGeocodingClient
from app.adapters.llm import MockLLMClient
from app.adapters.routing import MockRoutingClient
from app.adapters.sms import MockSmsClient
from app.adapters.types import LatLon


def test_factories_return_mocks_by_default():
    assert isinstance(get_llm_client(), MockLLMClient)
    assert isinstance(get_routing_client(), MockRoutingClient)
    assert isinstance(get_geocoding_client(), MockGeocodingClient)
    assert isinstance(get_sms_client(), MockSmsClient)


def test_mock_llm_returns_canned_response():
    assert MockLLMClient().complete("s", "u") == "{}"
    assert MockLLMClient('{"a": 1}').complete("s", "u") == '{"a": 1}'


def test_mock_llm_is_dumb_and_accepts_responder():
    assert MockLLMClient().complete('"patient" "visit_request"', "u") == "{}"
    assert MockLLMClient(responder=lambda s, u: f"{s}|{u}").complete("s", "u") == "s|u"


def test_mock_geocoding_matches_whole_words_only():
    geo = MockGeocodingClient()
    assert geo.geocode_address("Ličko-senjska županija") is None
    for query, settlement in (
        ("Senj", "Senj"),
        ("u Senju", "Senj"),
        ("53270", "Senj"),
        ("Donji Kosinj bb", "Donji Kosinj"),
        ("Lički Osik", "Lički Osik"),
    ):
        found = geo.geocode_address(query)
        assert found is not None and found.settlement == settlement, query


def test_mock_routing_matrix_shape_and_plausible_values():
    geo = MockGeocodingClient()
    gospic = geo.geocode("Gospić")
    otocac = geo.geocode("Otočac")
    senj = geo.geocode("Senj")
    pts = [gospic, otocac, senj]
    m = MockRoutingClient().matrix(pts)
    n = len(pts)
    assert len(m.durations_s) == n and all(len(r) == n for r in m.durations_s)
    assert len(m.distances_m) == n and all(len(r) == n for r in m.distances_m)
    for i in range(n):
        assert m.durations_s[i][i] == 0 and m.distances_m[i][i] == 0
        for j in range(n):
            assert m.durations_s[i][j] == m.durations_s[j][i]
            assert m.distances_m[i][j] == m.distances_m[j][i]
    assert 40_000 <= m.distances_m[0][1] <= 80_000
    assert 45 * 60 <= m.durations_s[0][1] <= 100 * 60


def test_mock_routing_empty_input():
    m = MockRoutingClient().matrix([])
    assert m.durations_s == [] and m.distances_m == []


def test_mock_geocoding():
    geo = MockGeocodingClient()
    assert isinstance(geo.geocode("Ulica 1, 53000 GOSPIĆ"), LatLon)
    assert geo.geocode("Gospic") == geo.geocode("gospić")
    assert geo.geocode("Zagreb") is None


def test_mock_sms_outbox_and_no_pii_in_logs(caplog):
    sms = MockSmsClient()
    phone, text = "+385 00 000 0001", "Probna poruka br. 12345"
    with caplog.at_level(logging.DEBUG):
        message_id = sms.send(phone, text)
    assert [(s.id, s.to, s.text) for s in sms.outbox] == [(message_id, phone, text)]
    assert sms.outbox[0].sent_at.tzinfo is not None
    assert message_id in caplog.text
    assert phone not in caplog.text
    assert text not in caplog.text
