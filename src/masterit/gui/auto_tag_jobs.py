from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import QObject, QRunnable, Signal

from masterit.cancellation import CancelToken
from masterit.library.move_work import MoveWork
from masterit.library.relocation import FolderCheck
from masterit.repack.pipeline import RepackPlan
from masterit.tagging.tagger import Tagger


class AutoTagSignals(QObject):
    move_progress = Signal(int, int)
    moved = Signal(object)
    event_received = Signal(object)
    crashed = Signal(str)
    finished = Signal()


type JobStep = Callable[[AutoTagSignals], None]


class TagRunJob(QRunnable):
    def __init__(self, step: JobStep) -> None:
        super().__init__()
        self.signals = AutoTagSignals()
        self._step = step

    @override
    def run(self) -> None:
        try:
            self._step(self.signals)
        except Exception as error:
            self.signals.crashed.emit(str(error))
        finally:
            self.signals.finished.emit()


def make_tag_step(tagger: Tagger, paths: list[Path], cancel_token: CancelToken) -> JobStep:
    def tag(signals: AutoTagSignals) -> None:
        if paths:
            tagger.tag(paths, signals.event_received.emit, cancel_token)

    return tag


def create_auto_tag_job(tagger: Tagger, paths: list[Path], cancel_token: CancelToken) -> TagRunJob:
    return TagRunJob(make_tag_step(tagger, paths, cancel_token))


def create_repack_job(
    plan: RepackPlan,
    cleanup_boundary: Path | None,
    is_protected: FolderCheck,
    tagger: Tagger,
    cancel_token: CancelToken,
) -> TagRunJob:
    move_work = MoveWork(plan.moves, cleanup_boundary, is_protected)

    def move_then_tag(signals: AutoTagSignals) -> None:
        try:
            move_work.run(signals.move_progress.emit)
        finally:
            signals.moved.emit(move_work.outcomes)
        if not cancel_token.is_cancelled:
            files = plan.get_files_to_tag(move_work.outcomes)
            make_tag_step(tagger, files, cancel_token)(signals)

    return TagRunJob(move_then_tag)
