import math
import time
from collections.abc import Callable
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


SYSTEM_CLOCK = SystemClock()


# Spaces task starts; the tagger runs files one at a time, so no lock is needed.
class RateLimiter:
    def __init__(self, interval: float, clock: Clock = SYSTEM_CLOCK) -> None:
        self._interval = interval
        self._clock = clock
        self._last_started_at = -math.inf

    def run[Result](self, task: Callable[[], Result]) -> Result:
        remaining_wait = self._interval - (self._clock.now() - self._last_started_at)
        if remaining_wait > 0:
            self._clock.sleep(remaining_wait)
        self._last_started_at = self._clock.now()
        return task()
