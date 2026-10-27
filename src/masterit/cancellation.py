import threading


class CancelToken:
    def __init__(self) -> None:
        self._requests = 0
        self._changed = threading.Condition()

    def cancel(self) -> None:
        with self._changed:
            self._requests += 1
            self._changed.notify_all()

    @property
    def is_cancelled(self) -> bool:
        return self._requests > 0

    def wait_cancelled(self, timeout: float) -> bool:
        return self.wait_for_request(0, timeout) > 0

    def wait_for_request(self, seen: int, timeout: float) -> int:
        """Waits for more than `seen` cancel requests; returns the current count."""
        with self._changed:
            self._changed.wait_for(lambda: self._requests > seen, timeout)
            return self._requests
