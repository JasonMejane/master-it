from collections.abc import Callable, Iterable
from pathlib import Path


class FileCache[T]:
    def __init__(self, read: Callable[[Path], T]) -> None:
        self._read = read
        self._values: dict[Path, T] = {}

    def get(self, path: Path) -> T:
        if path not in self._values:
            self._values[path] = self._read(path)
        return self._values[path]

    def forget(self, paths: Iterable[Path]) -> None:
        for path in paths:
            self._values.pop(path, None)

    def clear(self) -> None:
        self._values.clear()
