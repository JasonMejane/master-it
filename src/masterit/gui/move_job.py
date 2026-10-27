from pathlib import Path
from typing import override

from PySide6.QtCore import QObject, QRunnable, Signal

from masterit.library.relocation import (
    FolderCheck,
    RelocationOutcome,
    RelocationPlan,
    relocate_file,
    remove_emptied_folders,
)


class MoveSignals(QObject):
    progress = Signal(int, int)
    crashed = Signal(str)
    finished = Signal(object)


class MoveJob(QRunnable):
    def __init__(
        self, plan: RelocationPlan, cleanup_boundary: Path | None, is_protected: FolderCheck
    ) -> None:
        super().__init__()
        self.signals = MoveSignals()
        self._plan = plan
        self._cleanup_boundary = cleanup_boundary
        self._is_protected = is_protected
        self._outcomes: list[RelocationOutcome] = []

    @override
    def run(self) -> None:
        try:
            self._move_files()
            self._clean_up()
        except Exception as error:
            self.signals.crashed.emit(str(error))
        finally:
            self.signals.finished.emit(self._outcomes)

    def _move_files(self) -> None:
        entries = self._plan.valid_entries
        for done, entry in enumerate(entries, start=1):
            self._outcomes.append(relocate_file(entry.source, entry.target))
            self.signals.progress.emit(done, len(entries))

    def _clean_up(self) -> None:
        if self._cleanup_boundary is not None:
            remove_emptied_folders(self._outcomes, self._cleanup_boundary, self._is_protected)
