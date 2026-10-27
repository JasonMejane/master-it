import io
import urllib.request
from email.message import Message
from http.client import HTTPMessage, IncompleteRead
from typing import Any, cast
from urllib.error import HTTPError, URLError

import pytest

from masterit.tagging.web.errors import ServiceError, ServiceTimeoutError
from masterit.tagging.web.transport import (
    API_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    HttpRequest,
    HttpResponse,
    UrllibTransport,
    WebOnlyRedirectHandler,
    build_web_opener,
)

from .fakes import FakeClock

URL = "https://example.test/search"


def make_headers(values: dict[str, str]) -> Message:
    headers = Message()
    for name, value in values.items():
        headers[name] = value
    return headers


class FakeReply(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers: dict[str, str] | None = None):
        super().__init__(body)
        self.status = status
        self.headers = make_headers(headers or {})


class FakeOpener:
    def __init__(self, reply: Any = None, error: BaseException | None = None) -> None:
        self.reply = reply
        self.error = error
        self.requests: list[tuple[urllib.request.Request, float]] = []

    def __call__(self, url: urllib.request.Request, timeout: float) -> Any:
        self.requests.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self.reply


def send(opener: FakeOpener, request: HttpRequest | None = None) -> HttpResponse:
    return UrllibTransport(opener, FakeClock()).send(request or HttpRequest(URL))


def get_sent_url(url: str) -> str:
    opener = FakeOpener(FakeReply(b""))
    send(opener, HttpRequest(url))
    return opener.requests[0][0].full_url


def test_sends_url_headers_and_timeout():
    opener = FakeOpener(FakeReply(b"{}"))
    send(opener, HttpRequest(URL, {"User-Agent": "MasterIt"}, timeout=3.0))
    request, timeout = opener.requests[0]
    assert request.full_url == URL
    assert request.get_header("User-agent") == "MasterIt"
    assert timeout == 3.0


def test_api_requests_time_out_after_six_seconds():
    assert HttpRequest(URL).timeout == API_TIMEOUT_SECONDS == 6.0


def test_returns_status_lowercased_headers_and_body():
    reply = FakeReply(b"body", 201, {"Content-Type": "image/png"})
    response = send(FakeOpener(reply))
    assert response == HttpResponse(201, {"content-type": "image/png"}, b"body")


def test_http_error_statuses_are_responses():
    error = HTTPError(URL, 503, "busy", make_headers({"Retry-After": "3"}), io.BytesIO(b"x"))
    response = send(FakeOpener(error=error))
    assert (response.status, response.get_header("retry-after"), response.body) == (503, "3", b"x")
    assert not response.is_ok


def test_success_statuses_are_ok():
    assert HttpResponse(204, {}, b"").is_ok
    assert not HttpResponse(301, {}, b"").is_ok


def test_missing_header_reads_as_empty():
    assert HttpResponse(200, {}, b"").get_header("retry-after") == ""


@pytest.mark.parametrize(
    "error",
    [TimeoutError(), URLError(TimeoutError()), TimeoutError("read")],
)
def test_timeouts_become_service_timeouts(error: BaseException):
    with pytest.raises(ServiceTimeoutError, match="timed out"):
        send(FakeOpener(error=error))


@pytest.mark.parametrize(
    "error",
    [URLError("name not resolved"), ConnectionResetError("reset"), IncompleteRead(b"")],
)
def test_network_failures_become_service_errors(error: BaseException):
    with pytest.raises(ServiceError) as raised:
        send(FakeOpener(error=error))
    assert not isinstance(raised.value, ServiceTimeoutError)


def test_body_that_breaks_off_becomes_service_error():
    class BrokenReply(FakeReply):
        def read1(self, size: int | None = -1, /) -> bytes:
            raise ConnectionResetError("terminated")

    with pytest.raises(ServiceError, match="terminated"):
        send(FakeOpener(BrokenReply(b"")))


def test_byte_limit_is_exclusive():
    with pytest.raises(ServiceError, match="too large"):
        send(FakeOpener(FakeReply(bytes(10))), HttpRequest(URL, byte_limit=10))
    response = send(FakeOpener(FakeReply(bytes(9))), HttpRequest(URL, byte_limit=10))
    assert len(response.body) == 9


class CountingReply(FakeReply):
    read_bytes = 0

    def read1(self, size: int | None = -1, /) -> bytes:
        chunk = super().read1(size)
        self.read_bytes += len(chunk)
        return chunk


def test_byte_limit_stops_reading_early():

    reply = CountingReply(bytes(1_000_000))
    with pytest.raises(ServiceError, match="too large"):
        send(FakeOpener(reply), HttpRequest(URL, byte_limit=10))
    assert reply.read_bytes < 1_000_000


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.test/a", "cover.jpg"])
def test_refuses_urls_that_are_not_web_urls(url: str):
    opener = FakeOpener(FakeReply(b""))
    with pytest.raises(ServiceError, match="Unsupported URL"):
        send(opener, HttpRequest(url))
    assert opener.requests == []


def test_accepts_plain_http_urls():
    opener = FakeOpener(FakeReply(b""))
    send(opener, HttpRequest("HTTP://example.test/cover.jpg"))
    assert len(opener.requests) == 1


def test_reply_is_closed():
    reply = FakeReply(b"{}")
    send(FakeOpener(reply))
    assert reply.closed


def test_sends_a_default_user_agent():
    opener = FakeOpener(FakeReply(b""))
    send(opener)
    assert opener.requests[0][0].get_header("User-agent") == DEFAULT_USER_AGENT == "MasterIt"


def test_http_error_reply_is_closed():
    body = io.BytesIO(b"x")
    send(FakeOpener(error=HTTPError(URL, 404, "missing", make_headers({}), body)))
    assert body.closed


@pytest.mark.parametrize(
    "error",
    [UnicodeEncodeError("ascii", "é", 0, 1, "bad"), ValueError("bad URL")],
)
def test_value_errors_from_urllib_become_service_errors(error: BaseException):
    with pytest.raises(ServiceError):
        send(FakeOpener(error=error))


def test_malformed_url_becomes_service_error():
    with pytest.raises(ServiceError):
        send(FakeOpener(FakeReply(b"")), HttpRequest("http://[::1"))


def test_encodes_spaces_and_non_ascii_like_browsers():
    sent_url = get_sent_url("https://example.test/a b/café.jpg?q=é x&r=1#top")
    assert sent_url == "https://example.test/a%20b/caf%C3%A9.jpg?q=%C3%A9%20x&r=1#top"


def test_keeps_existing_escapes():
    assert get_sent_url("https://example.test/a%20b?q=%2F") == "https://example.test/a%20b?q=%2F"


def test_head_check_runs_before_the_body_is_read():
    def refuse(status: int, _headers: object) -> None:
        raise ServiceError(f"refused {status}")

    reply = CountingReply(b"page", 404, {"Content-Type": "text/html"})
    with pytest.raises(ServiceError, match="refused 404"):
        send(FakeOpener(reply), HttpRequest(URL, check_head=refuse))
    assert reply.read_bytes == 0
    assert reply.closed


def test_whole_request_must_finish_before_its_timeout():
    clock = FakeClock()

    class TricklingReply(FakeReply):
        def read1(self, size: int | None = -1, /) -> bytes:
            clock.advance(0.6)
            return super().read1(1)

    transport = UrllibTransport(FakeOpener(TricklingReply(b"abc")), clock)
    with pytest.raises(ServiceTimeoutError):
        transport.send(HttpRequest(URL, timeout=1.0))


def make_redirect(new_url: str) -> urllib.request.Request | None:
    request = urllib.request.Request(URL)
    return WebOnlyRedirectHandler().redirect_request(
        request, io.BytesIO(), 302, "Found", HTTPMessage(), new_url
    )


def test_redirects_stay_on_web_urls():
    with pytest.raises(ServiceError, match="Unsupported URL"):
        make_redirect("ftp://example.test/cover.jpg")
    redirect = make_redirect("https://cdn.example.test/cover.jpg")
    assert redirect is not None
    assert redirect.full_url == "https://cdn.example.test/cover.jpg"


def test_web_opener_follows_only_web_redirects():
    handlers = cast(list[urllib.request.BaseHandler], vars(build_web_opener())["handlers"])
    assert any(isinstance(handler, WebOnlyRedirectHandler) for handler in handlers)
    assert not any(type(handler) is urllib.request.HTTPRedirectHandler for handler in handlers)


def test_leaves_the_host_to_idna_encoding():
    assert get_sent_url("https://café.test/a b") == "https://café.test/a%20b"


def test_slow_headers_count_toward_the_timeout():
    clock = FakeClock()

    def open_slowly(url: urllib.request.Request, timeout: float) -> FakeReply:
        clock.advance(1.5)
        return FakeReply(b"")

    with pytest.raises(ServiceTimeoutError):
        UrllibTransport(open_slowly, clock).send(HttpRequest(URL, timeout=1.0))
