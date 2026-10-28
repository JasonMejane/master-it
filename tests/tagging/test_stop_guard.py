import threading
import time

import pytest

from masterit.cancellation import CancelToken
from masterit.tagging.stop_guard import (
    RunAbortedError,
    StopGuard,
    StoppableClock,
    StoppableTransport,
)
from masterit.tagging.web.transport import HttpRequest, HttpResponse

from .web.fakes import FakeTransport


def make_guard(requests: int = 0) -> StopGuard:
    token = CancelToken()
    for _ in range(requests):
        token.cancel()
    guard = StopGuard()
    guard.watch(token)
    return guard


def answer(_request: HttpRequest) -> HttpResponse:
    return HttpResponse(200, {}, b"{}")


@pytest.mark.parametrize("requests", [0, 1])
def test_lets_work_go_on_until_a_second_stop(requests: int):
    guard = make_guard(requests)
    guard.ensure_running()
    transport = FakeTransport(answer)
    StoppableTransport(transport, guard).send(HttpRequest("https://example.test"))
    assert len(transport.requests) == 1


def test_aborts_requests_after_a_second_stop():
    transport = FakeTransport(answer)
    with pytest.raises(RunAbortedError):
        StoppableTransport(transport, make_guard(2)).send(HttpRequest("https://example.test"))
    assert transport.requests == []


def test_waits_the_whole_time_without_a_second_stop():
    clock = StoppableClock(make_guard(1))
    started = clock.now()
    clock.sleep(0.05)
    assert clock.now() - started >= 0.04


def test_a_second_stop_wakes_a_wait_and_aborts():
    token = CancelToken()
    guard = StopGuard()
    guard.watch(token)
    token.cancel()
    threading.Timer(0.05, token.cancel).start()
    started = time.monotonic()
    with pytest.raises(RunAbortedError):
        StoppableClock(guard).sleep(10)
    assert time.monotonic() - started < 5


def test_an_unwatched_guard_never_aborts():
    StopGuard().ensure_running()
