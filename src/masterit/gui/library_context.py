from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from masterit.library.relocation import RelocationOutcome, RelocationPlan
from masterit.tags.fields import Tags
from masterit.tags.tag_edits import TagOutcome


class LibraryContext(Protocol):
    @property
    def is_busy(self) -> bool: ...

    def get_selected_paths(self) -> list[Path]: ...

    def show_status(self, text: str) -> None: ...


class RelocationContext(LibraryContext, Protocol):
    @property
    def opened_folder(self) -> Path | None: ...

    def show_preview(self, plan: RelocationPlan) -> None: ...

    def finish_relocation(
        self, verb: str, outcomes: list[RelocationOutcome], skipped: int
    ) -> None: ...


class TagContext(LibraryContext, Protocol):
    def get_tags(self, path: Path) -> Tags: ...

    def show_tag_preview(self, paths: Iterable[Path], edits: Tags) -> None: ...

    def finish_tagging(self, paths: list[Path], outcomes: list[TagOutcome]) -> None: ...
