import json
import threading
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from aos_api.rest_connector import HttpResponse, Pagination, RestConnectorError, RestGetEngine, RestRequest, SafeUrlPolicy


def policy():
    return SafeUrlPolicy(resolver=lambda *_: [(None, None, None, None, ("93.184.216.34", 443))])


def response(data, status=200, headers=None):
    return HttpResponse(status, headers or {}, json.dumps(data).encode(), "https://api.example.test/data")


@pytest.mark.parametrize("mode", ["page", "offset"])
def test_page_and_offset_pagination(mode):
    calls = []
    def transport(url, _headers, _timeout):
        calls.append(url); query = parse_qs(urlsplit(url).query)
        index = int(query.get("page", [1])[0]) if mode == "page" else int(query.get("offset", [0])[0]) // 2 + 1
        return response({"items": [{"id": index * 2 - 1}, {"id": index * 2}] if index < 3 else []})
    result = RestGetEngine(transport=transport, policy=policy()).fetch(
        RestRequest("https://api.example.test/data", response_path="items", pagination=Pagination(mode=mode, page_size=2)),
        org_workspace="o/w", connection_id="c")
    assert [x["id"] for x in result.items] == [1, 2, 3, 4]
    assert result.pages == 3


def test_cursor_pagination_and_repeated_cursor_guard():
    calls = 0
    def transport(*_):
        nonlocal calls; calls += 1
        return response({"items": [{"id": calls}], "next": "same"})
    with pytest.raises(RestConnectorError, match="CONNECTOR_CURSOR_REPEATED"):
        RestGetEngine(transport=transport, policy=policy()).fetch(
            RestRequest("https://api.example.test/data", response_path="items", pagination=Pagination(mode="cursor", next_cursor_path="next")),
            org_workspace="o/w", connection_id="c")


def test_429_retry_after_then_5xx_then_success():
    statuses = [response({}, 429, {"Retry-After": "2"}), response({}, 503), response([{"id": 1}])]
    slept = []
    engine = RestGetEngine(transport=lambda *_: statuses.pop(0), policy=policy(), sleep=slept.append, jitter=lambda: 0)
    result = engine.fetch(RestRequest("https://api.example.test/data", max_attempts=3), org_workspace="o/w", connection_id="c")
    assert result.items == [{"id": 1}]
    assert slept == [2, 2]


def test_429_retry_after_http_date():
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=2)
    replies = [response({}, 429, {"Retry-After": retry_at.strftime("%a, %d %b %Y %H:%M:%S GMT")}), response([])]
    slept = []
    RestGetEngine(transport=lambda *_: replies.pop(0), policy=policy(), sleep=slept.append).fetch(
        RestRequest("https://api.example.test/data", max_attempts=2), org_workspace="o/w", connection_id="c")
    assert 0 <= slept[0] <= 2


def test_non_retryable_and_timeout_deadline():
    with pytest.raises(RestConnectorError) as rejected:
        RestGetEngine(transport=lambda *_: response({}, 401), policy=policy()).fetch(RestRequest("https://api.example.test/data"), org_workspace="o/w", connection_id="c")
    assert rejected.value.code == "CONNECTOR_UPSTREAM_REJECTED"
    clock = iter([0, 0, 0, 10])
    with pytest.raises(RestConnectorError) as timed:
        RestGetEngine(transport=lambda *_: (_ for _ in ()).throw(TimeoutError()), policy=policy(), clock=lambda: next(clock), sleep=lambda _: None, jitter=lambda: 0).fetch(
            RestRequest("https://api.example.test/data", deadline=1), org_workspace="o/w", connection_id="c")
    assert timed.value.code in {"CONNECTOR_DEADLINE_EXCEEDED", "CONNECTOR_TIMEOUT"}


def test_ssrf_and_redirect_are_rejected():
    with pytest.raises(RestConnectorError, match="CONNECTOR_URL_FORBIDDEN"):
        SafeUrlPolicy(resolver=lambda *_: [(None, None, None, None, ("127.0.0.1", 443))]).validate("https://example.test")
    redirected = HttpResponse(200, {}, b"[]", "http://169.254.169.254/latest")
    with pytest.raises(RestConnectorError, match="CONNECTOR_URL_FORBIDDEN"):
        RestGetEngine(transport=lambda *_: redirected, policy=policy()).fetch(RestRequest("https://api.example.test/data"), org_workspace="o/w", connection_id="c")


def test_legacy_env_adapter_remains_compatible(monkeypatch):
    from aos_api import connector_runtime
    from aos_api.errors import ApiError

    monkeypatch.delenv("AOS_REST_CONNECTOR_URL", raising=False)
    monkeypatch.delenv("AOS_REST_CONNECTOR_MOCK", raising=False)
    with pytest.raises(ApiError) as missing:
        connector_runtime._rest_http_get()
    assert missing.value.status_code == 501

    monkeypatch.setenv("AOS_REST_CONNECTOR_URL", "http://rest.test/data")
    class LegacyResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self): return b'{"items":[{"id":1}]}'
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: LegacyResponse())
    result = connector_runtime._rest_http_get()
    assert result["sample"]["items"][0]["id"] == 1


def test_rate_limit_is_scoped_by_workspace_and_connection():
    class FakeTime:
        value = 0.0
        def now(self): return self.value
        def sleep(self, delay): self.value += delay
    fake = FakeTime()
    engine = RestGetEngine(transport=lambda *_: response([]), policy=policy(), clock=fake.now, sleep=fake.sleep)
    spec = RestRequest("https://api.example.test/data", qps=1)
    engine.fetch(spec, org_workspace="o/w", connection_id="c")
    engine.fetch(spec, org_workspace="o/w", connection_id="c")
    assert fake.value == 1
    engine.fetch(spec, org_workspace="o/other", connection_id="c")
    assert fake.value == 1


def test_rate_limit_state_is_serialized_for_concurrent_requests():
    calls = []
    gate = threading.Barrier(3)
    engine = RestGetEngine(transport=lambda *_: calls.append(time.monotonic()) or response([]), policy=policy())
    spec = RestRequest("https://api.example.test/data", qps=50)
    def run():
        gate.wait()
        engine.fetch(spec, org_workspace="o/w", connection_id="c")
    threads = [threading.Thread(target=run) for _ in range(2)]
    [thread.start() for thread in threads]
    gate.wait()
    [thread.join() for thread in threads]
    assert len(calls) == 2
    assert abs(calls[1] - calls[0]) >= 0.015
