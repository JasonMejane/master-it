import time

from masterit.cancellation import CancelToken
from masterit.tagging.web.transport import HttpRequest, HttpResponse, HttpTransport

# The first stop request ends the run after the current file; the second abandons that file.
ABORTING_REQUESTS = 2


# Per-file error handlers let it through: an abandoned file is not a failed one.
class RunAbortedError(Exception):
    pass


class StopGuard:
    def __init__(self) -> None:
        self._token = CancelToken()

    def watch(self, token: CancelToken) -> None:
        self._token = token

    def ensure_running(self) -> None:
        if self._token.wait_for_request(0, 0) >= ABORTING_REQUESTS:
            raise RunAbortedError

    def wait(self, seconds: float) -> None:
        requests = self._token.wait_for_request(ABORTING_REQUESTS - 1, seconds)
        if requests >= ABORTING_REQUESTS:
            raise RunAbortedError


# Rate-limit waits wake at once when the run is abandoned.
class StoppableClock:
    def __init__(self, guard: StopGuard) -> None:
        self._guard = guard

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        self._guard.wait(seconds)


# A request already sent still ends within its timeout; none starts once the run is abandoned.
class StoppableTransport:
    def __init__(self, transport: HttpTransport, guard: StopGuard) -> None:
        self._transport = transport
        self._guard = guard

    def send(self, request: HttpRequest) -> HttpResponse:
        self._guard.ensure_running()
        return self._transport.send(request)
