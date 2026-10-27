from collections.abc import Iterable
from pathlib import Path

from masterit.tags.fields import Tags
from masterit.tags.tag_store import TagError, TagStore


class TagCache:
    def __init__(self, store: TagStore) -> None:
        self._store = store
        self._tags: dict[Path, Tags] = {}

    def get(self, path: Path) -> Tags:
        if path not in self._tags:
            self._tags[path] = self._read(path)
        return self._tags[path]

    def forget(self, paths: Iterable[Path]) -> None:
        for path in paths:
            self._tags.pop(path, None)

    def clear(self) -> None:
        self._tags.clear()

    def _read(self, path: Path) -> Tags:
        try:
            return self._store.read(path)
        except TagError:
            return {}
