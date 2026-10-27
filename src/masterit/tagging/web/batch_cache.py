from collections.abc import Callable
from typing import cast


# Callers namespace their keys, so each key always holds the same value type.
class BatchCache:
    def __init__(self) -> None:
        self._entries: dict[str, object] = {}

    def get_or_load[Value](self, key: str, load: Callable[[], Value]) -> Value:
        if key not in self._entries:
            self._entries[key] = load()
        return cast(Value, self._entries[key])

    def clear(self) -> None:
        self._entries.clear()
