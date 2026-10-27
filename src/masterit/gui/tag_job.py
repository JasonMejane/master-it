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
    def __init__(self, paths: list[Path], edits: Tags, store: TagStore) -> None:
        super().__init__()
        self.signals = TagSignals()
        self._paths = paths
        self._edits = edits
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
        for done, path in enumerate(self._paths, start=1):
            self._outcomes.append(write_tag_edits(path, self._edits, self._store))
            self.signals.progress.emit(done, len(self._paths))
