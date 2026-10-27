from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QPushButton, QWidget

from masterit.gui.library_context import RelocationContext
from masterit.gui.move_dialog import confirm_move
from masterit.gui.move_job import MoveJob
from masterit.library.destinations import make_move_destination
from masterit.library.relocation import (
    FolderCheck,
    RelocationOutcome,
    RelocationPlan,
    make_relocation_plan,
)

type MoveConfirmation = Callable[[QWidget, RelocationPlan, Path], bool]


def make_download_protection(
    download_folder: Path, is_downloading: Callable[[], bool]
) -> FolderCheck:
    protected_root = download_folder.resolve()

    def is_protected(folder: Path) -> bool:
        is_download_tree = folder.is_relative_to(protected_root) and is_downloading()
        return folder == protected_root or is_download_tree

    return is_protected


class MoveAction(QWidget):
    started = Signal()
    finished = Signal()

    def __init__(
        self,
        context: RelocationContext,
        get_download_folder: Callable[[], Path],
        is_downloading: Callable[[], bool],
        thread_pool: QThreadPool,
        confirm: MoveConfirmation = confirm_move,
    ) -> None:
        super().__init__()
        self._context = context
        self._get_download_folder = get_download_folder
        self._is_downloading = is_downloading
        self._thread_pool = thread_pool
        self._confirm_move = confirm
        self._move_job: MoveJob | None = None
        self._move_crash = ""
        self._move_skipped = 0
        self.move_button = QPushButton("Move selected to…")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.move_button)
        self.move_button.clicked.connect(self.start_move)

    @property
    def is_moving(self) -> bool:
        return self._move_job is not None

    def start_move(self) -> None:
        if not self._context.get_selected_paths():
            self._context.show_status("Select files to move.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Move to")
        if folder:
            self._confirm_and_move(Path(folder))

    def _confirm_and_move(self, folder: Path) -> None:
        # Read after the dialog: its event loop may have run a pending rename.
        paths = self._context.get_selected_paths()
        plan = make_relocation_plan(paths, make_move_destination(folder))
        if self._confirm_move(self, plan, folder):
            self._start_move_job(plan)

    def _start_move_job(self, plan: RelocationPlan) -> None:
        protection = make_download_protection(self._get_download_folder(), self._is_downloading)
        cleanup_root = self._context.opened_folder or self._get_download_folder()
        job = MoveJob(plan, cleanup_root, protection)
        job.signals.progress.connect(self._show_move_progress)
        job.signals.crashed.connect(self._remember_move_crash)
        job.signals.finished.connect(self._finish_move)
        self._move_job = job
        self._move_skipped = len(plan.entries) - len(plan.valid_entries)
        self._move_crash = ""
        self.started.emit()
        self._show_move_progress(0, len(plan.valid_entries))
        self._thread_pool.start(job)

    def _show_move_progress(self, done: int, total: int) -> None:
        self._context.show_status(f"Moving {done}/{total}…")

    def _remember_move_crash(self, message: str) -> None:
        self._move_crash = message

    def _finish_move(self, outcomes: list[RelocationOutcome]) -> None:
        self._move_job = None
        self._context.finish_relocation("moved", outcomes, self._move_skipped)
        if self._move_crash:
            self._context.show_status(f"Move stopped by an unexpected error: {self._move_crash}")
        self.finished.emit()
