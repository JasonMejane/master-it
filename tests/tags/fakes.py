from pathlib import Path

from masterit.tags.fields import Tags
from masterit.tags.tag_store import TagError


class FakeTagStore:
    def __init__(self, tags: dict[Path, Tags] | None = None, failing: set[Path] | None = None):
        self.tags = {path: dict(values) for path, values in (tags or {}).items()}
        self.reads: list[Path] = []
        self.failing = failing or set()

    def read(self, path: Path) -> Tags:
        self.reads.append(path)
        if path in self.failing:
            raise TagError("unreadable")
        return dict(self.tags.get(path, {}))

    def write(self, path: Path, changes: Tags) -> None:
        if path in self.failing:
            raise TagError("read-only")
        self.tags[path] = {**self.tags.get(path, {}), **changes}
