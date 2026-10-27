from collections.abc import Callable
from pathlib import Path

from masterit.library.relocation import (
    FolderCheck,
    RelocationOutcome,
    RelocationPlan,
    relocate_file,
    remove_emptied_folders,
)

type ProgressHandler = Callable[[int, int], None]


class MoveWork:
    def __init__(
        self, plan: RelocationPlan, cleanup_boundary: Path | None, is_protected: FolderCheck
    ) -> None:
        self._plan = plan
        self._cleanup_boundary = cleanup_boundary
        self._is_protected = is_protected
        # Filled as files move, so a crash still reports the files already moved.
        self.outcomes: list[RelocationOutcome] = []

    def run(self, on_progress: ProgressHandler) -> None:
        self._move_files(on_progress)
        self._clean_up()

    def _move_files(self, on_progress: ProgressHandler) -> None:
        entries = self._plan.valid_entries
        for done, entry in enumerate(entries, start=1):
            self.outcomes.append(relocate_file(entry.source, entry.target))
            on_progress(done, len(entries))

    def _clean_up(self) -> None:
        if self._cleanup_boundary is not None:
            remove_emptied_folders(self.outcomes, self._cleanup_boundary, self._is_protected)
