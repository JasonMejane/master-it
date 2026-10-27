import json
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
