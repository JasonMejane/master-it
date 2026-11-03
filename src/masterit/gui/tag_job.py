from pathlib import Path
from typing import override

from PySide6.QtCore import QObject, QRunnable, Signal

from masterit.tags.fields import Tags
from masterit.tags.tag_edits import TagOutcome, write_tag_edits
from masterit.tags.tag_store import TagStore


class TagSignals(QObject):
    progress = Signal(int, int)
    crashed = Signal(str)
    finished = Signal(object)


class TagJob(QRunnable):
    def __init__(self, edits_by_path: dict[Path, Tags], store: TagStore) -> None:
        super().__init__()
        self.signals = TagSignals()
        self._edits_by_path = edits_by_path
        self._store = store
        self._outcomes: list[TagOutcome] = []

    @override
    def run(self) -> None:
        try:
            self._write_tags()
        except Exception as error:
            self.signals.crashed.emit(str(error))
        finally:
            self.signals.finished.emit(self._outcomes)

    def _write_tags(self) -> None:
        total = len(self._edits_by_path)
        for done, (path, edits) in enumerate(self._edits_by_path.items(), start=1):
            self._outcomes.append(write_tag_edits(path, edits, self._store))
            self.signals.progress.emit(done, total)
