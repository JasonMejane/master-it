from functools import partial
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from masterit.cancellation import CancelToken
from masterit.gui.auto_tag_jobs import TagRunJob, create_auto_tag_job, create_repack_job
from masterit.gui.library_context import AutoTagContext
from masterit.gui.library_services import LibraryServices
from masterit.gui.move_action import make_download_protection
from masterit.gui.summaries import format_relocation_summary
from masterit.library.relocation import RelocationOutcome
from masterit.repack.pipeline import RepackPlan, make_repack_plan
from masterit.tagging.events import TaggerEvent
from masterit.tagging.run_tracker import AutoTagRun
from masterit.tagging.tagger import Tagger

NO_SOUNDTAG_HINT = "SoundTag not found on PATH"
STOPPING_NOTICE = "Stopping after the current file."
STOP_MESSAGES = (
    "Stopping after the current file… (Stop now quits at once)",
    "Stopping now…",
)


def describe_root(root: Path | None) -> str:
    return "No library root" if root is None else f"Library: {root}"


class AutoTagAction(QWidget):
    started = Signal()
    finished = Signal()

    def __init__(self, context: AutoTagContext, services: LibraryServices) -> None:
        super().__init__()
        self._context = context
        self._services = services
        self.confirm_repack = services.confirm_repack
        self._job: TagRunJob | None = None
        self._stop_requests = 0
        self._cancel_token = CancelToken()
        self._run = AutoTagRun()
        self._move_summary = ""
        self._crash = ""
        self._build_widgets()
        self._build_layout()
        self._connect_signals()
        self.root_label.setText(describe_root(services.root_store.load_library_root()))
        self.set_busy(False)

    @property
    def is_running(self) -> bool:
        return self._job is not None

    def set_busy(self, busy: bool) -> None:
        can_start = self._services.tagger is not None and not busy
        self.repack_button.setEnabled(can_start)
        self.auto_tag_button.setEnabled(can_start)
        self.root_button.setEnabled(not busy)
        self.cancel_button.setEnabled(self.is_running and self._stop_requests < len(STOP_MESSAGES))

    def choose_root(self) -> Path | None:
        folder = QFileDialog.getExistingDirectory(self, "Library root")
        if not folder:
            return None
        root = Path(folder)
        self._services.root_store.save_library_root(root)
        self.root_label.setText(describe_root(root))
        return root

    def start_repack(self) -> None:
        tagger = self._get_ready_tagger("Select files to repack.")
        if tagger is None:
            return
        root = self._services.root_store.load_library_root() or self.choose_root()
        if root is not None:
            self._confirm_and_repack(root, tagger)

    def start_auto_tag(self) -> None:
        tagger = self._get_ready_tagger("Select files to auto-tag.")
        if tagger is None:
            return
        paths = self._context.get_selected_paths()
        self._start_job(create_auto_tag_job(tagger, paths, self._renew_cancel_token()))
        self._context.show_auto_tag_statuses(self._run.add_pending(paths))

    def cancel(self) -> None:
        if not self.is_running or self._stop_requests >= len(STOP_MESSAGES):
            return
        self._cancel_token.cancel()
        self._context.show_status(STOP_MESSAGES[self._stop_requests])
        self._stop_requests += 1
        self.cancel_button.setText("Stop now")
        self.cancel_button.setEnabled(self._stop_requests < len(STOP_MESSAGES))

    def _get_ready_tagger(self, missing_selection: str) -> Tagger | None:
        if self._services.tagger is None:
            return None
        if not self._context.get_selected_paths():
            self._context.show_status(missing_selection)
            return None
        return self._services.tagger

    def _confirm_and_repack(self, root: Path, tagger: Tagger) -> None:
        # Read after the root dialog: its event loop may have changed the files.
        paths = self._context.get_selected_paths()
        plan = make_repack_plan(paths, root, self._context.get_tags)
        if self.confirm_repack(self, plan, root):
            self._start_repack_job(plan, tagger)

    def _start_repack_job(self, plan: RepackPlan, tagger: Tagger) -> None:
        services = self._services
        download_folder = services.get_download_folder()
        protection = make_download_protection(download_folder, services.is_downloading)
        cleanup_root = self._context.opened_folder or download_folder
        token = self._renew_cancel_token()
        job = create_repack_job(plan, cleanup_root, protection, tagger, token)
        skipped = len(plan.moves.entries) - len(plan.moves.valid_entries)
        job.signals.move_progress.connect(self._show_move_progress)
        job.signals.moved.connect(partial(self._finish_moves, plan, skipped))
        self._start_job(job)

    def _renew_cancel_token(self) -> CancelToken:
        self._cancel_token = CancelToken()
        return self._cancel_token

    def _start_job(self, job: TagRunJob) -> None:
        self._run = AutoTagRun()
        self._stop_requests = 0
        self._move_summary = ""
        self._crash = ""
        job.signals.event_received.connect(self.handle_event)
        job.signals.crashed.connect(self._remember_crash)
        job.signals.finished.connect(self._finish)
        self._job = job
        self.started.emit()
        self._services.thread_pool.start(job)

    def _show_move_progress(self, done: int, total: int) -> None:
        self._show_progress(f"Moving {done}/{total}…")

    def _show_progress(self, text: str) -> None:
        notice = f" {STOPPING_NOTICE}" if self._stop_requests else ""
        self._context.show_status(f"{text}{notice}")

    def _finish_moves(
        self, plan: RepackPlan, skipped: int, outcomes: list[RelocationOutcome]
    ) -> None:
        self._context.finish_relocation("moved", outcomes, skipped)
        self._move_summary = format_relocation_summary("moved", outcomes, skipped)
        pending = self._run.add_pending(plan.get_files_to_tag(outcomes))
        self._context.show_auto_tag_statuses(pending)

    def handle_event(self, event: TaggerEvent) -> None:
        self._context.show_auto_tag_statuses(self._run.apply(event))
        self._show_progress(self._run.progress_text)

    def _remember_crash(self, message: str) -> None:
        self._crash = message

    def _finish(self) -> None:
        self._job = None
        self.cancel_button.setText("Cancel")
        self._context.show_auto_tag_statuses(self._run.finish())
        self._context.refresh_tags(self._run.processed)
        self._context.show_status(self._describe_end())
        self.finished.emit()

    def _describe_end(self) -> str:
        crash = f"Auto-tag stopped by an unexpected error: {self._crash}"
        tag_summary = crash if self._crash else self._run.summary
        return f"{self._move_summary} {tag_summary}".strip()

    def _build_widgets(self) -> None:
        self.root_button = QPushButton("Library root…")
        self.root_label = QLabel()
        self.repack_button = QPushButton("Repack selected")
        self.auto_tag_button = QPushButton("Auto-tag selected")
        self.cancel_button = QPushButton("Cancel")
        if self._services.tagger is None:
            self.repack_button.setToolTip(NO_SOUNDTAG_HINT)
            self.auto_tag_button.setToolTip(NO_SOUNDTAG_HINT)

    def _build_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.root_button)
        layout.addWidget(self.root_label, stretch=1)
        layout.addWidget(self.repack_button)
        layout.addWidget(self.auto_tag_button)
        layout.addWidget(self.cancel_button)

    def _connect_signals(self) -> None:
        self.root_button.clicked.connect(self.choose_root)
        self.repack_button.clicked.connect(self.start_repack)
        self.auto_tag_button.clicked.connect(self.start_auto_tag)
        self.cancel_button.clicked.connect(self.cancel)
