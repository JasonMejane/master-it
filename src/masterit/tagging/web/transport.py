import math
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from email.message import Message
from http.client import HTTPException, HTTPMessage
from typing import IO, Any, Protocol, cast
from urllib.error import HTTPError, URLError

from masterit.tagging.web.errors import ServiceError, ServiceTimeoutError
from masterit.tagging.web.rate_limiter import SYSTEM_CLOCK, Clock

# Services that stall would hold up every file, while covers are larger downloads.
API_TIMEOUT_SECONDS = 6.0
IMAGE_TIMEOUT_SECONDS = 10.0
CHUNK_BYTES = 65_536
WEB_SCHEMES = ("http", "https")
DEFAULT_USER_AGENT = "MasterIt"
# Characters a URL may hold as they are; others are percent-encoded as browsers do.
URL_SAFE_CHARACTERS = ":/?#[]@!$&'()*+,;=%~"

type HeadCheck = Callable[[int, Mapping[str, str]], None]


def accept_any_head(_status: int, _headers: Mapping[str, str]) -> None:
    pass


@dataclass(frozen=True)
class HttpRequest:
    url: str
    headers: Mapping[str, str] = field(default_factory=dict[str, str])
    timeout: float = API_TIMEOUT_SECONDS
    byte_limit: float = math.inf
    check_head: HeadCheck = field(default=accept_any_head, compare=False)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    @property
    def is_ok(self) -> bool:
        return 200 <= self.status < 300

    def get_header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")


class HttpTransport(Protocol):
    def send(self, request: HttpRequest) -> HttpResponse: ...


class Reply(Protocol):
    @property
    def status(self) -> int | None: ...

    @property
    def headers(self) -> Message: ...

    def read1(self, size: int, /) -> bytes: ...

    def close(self) -> None: ...


class UrlOpener(Protocol):
    def __call__(self, url: urllib.request.Request, *, timeout: float) -> Any: ...


class WebOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        ensure_web_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def build_web_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(WebOnlyRedirectHandler)


class UrllibTransport:
    def __init__(self, open_url: UrlOpener | None = None, clock: Clock = SYSTEM_CLOCK) -> None:
        self._open_url = open_url or build_web_opener().open
        self._clock = clock

    def send(self, request: HttpRequest) -> HttpResponse:
        deadline = self._clock.now() + request.timeout
        try:
            reply = self._open(request)
            return self._read_reply(reply, request, deadline)
        except (OSError, HTTPException, ValueError) as error:
            raise make_service_error(error) from error

    def _open(self, request: HttpRequest) -> Reply:
        url = encode_url(request.url)
        headers = {"User-Agent": DEFAULT_USER_AGENT, **request.headers}
        url_request = urllib.request.Request(url, headers=headers)  # noqa: S310 - scheme checked
        try:
            return self._open_url(url_request, timeout=request.timeout)
        except HTTPError as error:
            return cast(Reply, error)  # read1 reaches its body through attribute delegation

    def _read_reply(self, reply: Reply, request: HttpRequest, deadline: float) -> HttpResponse:
        try:
            headers = {name.lower(): value for name, value in reply.headers.items()}
            status = reply.status or 0
            ensure_before_deadline(self._clock.now(), deadline)
            request.check_head(status, headers)
            return HttpResponse(status, headers, self._read_body(reply, request, deadline))
        finally:
            reply.close()

    # Socket timeouts only bound each read, so a trickling service needs a deadline.
    def _read_body(self, reply: Reply, request: HttpRequest, deadline: float) -> bytes:
        chunks: list[bytes] = []
        total_bytes = 0
        while chunk := reply.read1(CHUNK_BYTES):
            total_bytes += len(chunk)
            ensure_below_limit(total_bytes, request.byte_limit)
            ensure_before_deadline(self._clock.now(), deadline)
            chunks.append(chunk)
        return b"".join(chunks)


# Cover URLs come from service answers, which must never make the tagger read local files.
def ensure_web_url(url: str) -> None:
    if urllib.parse.urlsplit(url).scheme.lower() not in WEB_SCHEMES:
        raise ServiceError(f"Unsupported URL: {url}")


# The host is left to http.client, which IDNA-encodes it.
def encode_url(url: str) -> str:
    ensure_web_url(url)
    parts = urllib.parse.urlsplit(url)
    path, query, fragment = (
        urllib.parse.quote(part, safe=URL_SAFE_CHARACTERS)
        for part in (parts.path, parts.query, parts.fragment)
    )
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, fragment))


def ensure_below_limit(total_bytes: int, byte_limit: float) -> None:
    if total_bytes >= byte_limit:
        raise ServiceError("Response was too large.")


def ensure_before_deadline(now: float, deadline: float) -> None:
    if now > deadline:
        raise ServiceTimeoutError()


def make_service_error(error: OSError | HTTPException | ValueError) -> ServiceError:
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, TimeoutError):
        return ServiceTimeoutError()
    return ServiceError(str(error))
