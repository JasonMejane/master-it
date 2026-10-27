import pytest

from masterit.tagging.web.rate_limiter import SYSTEM_CLOCK, RateLimiter

from .fakes import FakeClock


def test_runs_first_task_without_waiting():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock)
    assert limiter.run(lambda: "done") == "done"
    assert clock.sleeps == []


def test_waits_for_remaining_interval_between_task_starts():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock)
    limiter.run(lambda: clock.advance(0.3))
    limiter.run(lambda: None)
    assert clock.sleeps == [pytest.approx(0.7)]


def test_does_not_wait_once_interval_elapsed():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock)
    limiter.run(lambda: None)
    clock.advance(1.5)
    limiter.run(lambda: None)
    assert clock.sleeps == []


def test_keeps_spacing_after_a_failed_task():
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock)

    def fail() -> None:
        raise RuntimeError("failed task")

    with pytest.raises(RuntimeError):
        limiter.run(fail)
    assert limiter.run(lambda: "next") == "next"
    assert clock.sleeps == [1.0]


def test_system_clock_sleeps_on_a_monotonic_clock():
    started_at = SYSTEM_CLOCK.now()
    SYSTEM_CLOCK.sleep(0.02)
    assert SYSTEM_CLOCK.now() - started_at >= 0.015
