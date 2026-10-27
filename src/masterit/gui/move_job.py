from pathlib import Path
from typing import override

from PySide6.QtCore import QObject, QRunnable, Signal

from masterit.library.move_work import MoveWork
from masterit.library.relocation import FolderCheck, RelocationPlan


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
        self._work = MoveWork(plan, cleanup_boundary, is_protected)

    @override
    def run(self) -> None:
        try:
            self._work.run(self.signals.progress.emit)
        except Exception as error:
            self.signals.crashed.emit(str(error))
        finally:
            self.signals.finished.emit(self._work.outcomes)
