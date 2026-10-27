import json
import urllib.parse
from collections.abc import Callable
from typing import Any

from masterit.tagging.web.transport import HttpRequest, HttpResponse


class FakeClock:
    def __init__(self) -> None:
        self.time = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.time += seconds

    def advance(self, seconds: float) -> None:
        self.time += seconds


type Responder = Callable[[HttpRequest], HttpResponse]


class FakeTransport:
    def __init__(self, respond: Responder) -> None:
        self._respond = respond
        self.requests: list[HttpRequest] = []

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        response = self._respond(request)
        request.check_head(response.status, response.headers)
        return response


def make_json_response(payload: Any, status: int = 200) -> HttpResponse:
    return HttpResponse(status, {"content-type": "application/json"}, json.dumps(payload).encode())


def make_image_response(body: bytes = b"image", status: int = 200) -> HttpResponse:
    return HttpResponse(status, {"content-type": "image/jpeg"}, body)


# Answers API paths of one host from `responses`, and serves any other host as an image.
class FakeWeb:
    def __init__(self, api_host: str, responses: dict[str, Any], missing: Any = None) -> None:
        self.api_host = api_host
        self.responses = responses
        self.missing: Any = {} if missing is None else missing
        self.requested: list[str] = []
        self.transport = FakeTransport(self._respond)

    def _respond(self, request: HttpRequest) -> HttpResponse:
        url = urllib.parse.urlsplit(request.url)
        self.requested.append(f"{url.path}?{url.query}" if url.query else url.path)
        if url.hostname != self.api_host:
            return make_image_response(f"image {url.path}".encode())
        return make_json_response(self.responses.get(url.path, self.missing))
