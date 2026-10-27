from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from masterit.gui.library_table_model import LibraryTableModel
from masterit.gui.move_dialog import confirm_move
from masterit.gui.move_job import MoveJob
from masterit.library.audio_files import list_audio_files
from masterit.library.destinations import make_move_destination, make_rename_destination
from masterit.library.relocation import (
    FolderCheck,
    RelocationOutcome,
    RelocationPlan,
    apply_relocation_plan,
    make_relocation_plan,
    replace_relocated_paths,
)
from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText, RenameRule, SetName

OPERATIONS = (("Remove text", RemoveText), ("Add prefix", AddPrefix), ("Add suffix", AddSuffix))
SESSION_LABEL = "This session's downloads"


def remove_extension(name: str, suffix: str) -> str:
    return name[: -len(suffix)] if name.lower().endswith(suffix.lower()) else name


type MoveConfirmation = Callable[[QWidget, RelocationPlan, Path], bool]


def keep_inside(paths: list[Path], folder: Path | None) -> list[Path]:
    if folder is None:
        return paths
    root = folder.resolve()
    return [path for path in paths if path.parent.resolve().is_relative_to(root)]


def make_download_protection(
    download_folder: Path, is_downloading: Callable[[], bool]
) -> FolderCheck:
    protected_root = download_folder.resolve()

    def is_protected(folder: Path) -> bool:
        is_download_tree = folder.is_relative_to(protected_root) and is_downloading()
        return folder == protected_root or is_download_tree

    return is_protected


def format_relocation_summary(verb: str, outcomes: list[RelocationOutcome], skipped: int) -> str:
    failures = [outcome for outcome in outcomes if not outcome.succeeded]
    succeeded = len(outcomes) - len(failures)
    summary = f"{succeeded} {verb}, {skipped} skipped, {len(failures)} failed."
    if not failures:
        return summary
    return f"{summary} {failures[0].source.name}: {failures[0].error}"


class LibraryPanel(QWidget):
    move_finished = Signal()

    def __init__(
        self,
        get_download_folder: Callable[[], Path],
        is_downloading: Callable[[], bool],
        thread_pool: QThreadPool,
        confirm: MoveConfirmation = confirm_move,
    ) -> None:
        super().__init__()
        self._get_download_folder = get_download_folder
        self._is_downloading = is_downloading
        self._thread_pool = thread_pool
        self._confirm_move = confirm
        self._session_files: list[Path] = []
        self._folder: Path | None = None
        self._plan = RelocationPlan(())
        self._move_job: MoveJob | None = None
        self._move_crash = ""
        self._move_skipped = 0
        self._build_widgets()
        self._build_layout()
        self._connect_signals()

    @property
    def is_moving(self) -> bool:
        return self._move_job is not None

    def add_downloaded_file(self, path: Path) -> None:
        if path in self._session_files:
            return
        self._session_files.append(path)
        if self._folder is None:
            self.table_model.append_file(path)

    def open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open folder")
        if folder:
            self._folder = Path(folder)
            self._reload_files()

    def show_session(self) -> None:
        self._folder = None
        self._reload_files()

    def refresh_preview(self) -> None:
        self._plan = make_relocation_plan(
            self._get_selected_paths(), make_rename_destination(self._make_rule())
        )
        self.table_model.set_preview(self._plan)
        self.apply_button.setEnabled(bool(self._plan.valid_entries) and not self.is_moving)

    def apply_rename(self) -> None:
        if self.is_moving:
            return
        skipped = len(self._plan.entries) - len(self._plan.valid_entries)
        self._finish_relocation("renamed", apply_relocation_plan(self._plan), skipped)
        self.rename_text_input.clear()

    def rename_single_file(self, path: Path, name: str) -> None:
        if not self.is_moving:
            self._rename_single_file(path, name)

    def _rename_single_file(self, path: Path, name: str) -> None:
        plan = make_relocation_plan(
            [path], make_rename_destination(SetName(remove_extension(name, path.suffix)))
        )
        problems = [str(entry.problem) for entry in plan.entries if not entry.is_valid]
        if problems:
            self.status_label.setText(problems[0])
            return
        if plan.entries:
            self._finish_relocation("renamed", apply_relocation_plan(plan), skipped=0)

    def start_move(self) -> None:
        if not self._get_selected_paths():
            self.status_label.setText("Select files to move.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Move to")
        if folder:
            self._confirm_and_move(Path(folder))

    def _confirm_and_move(self, folder: Path) -> None:
        # Read after the dialog: its event loop may have run a pending rename.
        plan = make_relocation_plan(self._get_selected_paths(), make_move_destination(folder))
        if self._confirm_move(self, plan, folder):
            self._start_move_job(plan)

    def _start_move_job(self, plan: RelocationPlan) -> None:
        protection = make_download_protection(self._get_download_folder(), self._is_downloading)
        job = MoveJob(plan, self._folder or self._get_download_folder(), protection)
        job.signals.progress.connect(self._show_move_progress)
        job.signals.crashed.connect(self._remember_move_crash)
        job.signals.finished.connect(self._finish_move)
        self._move_job = job
        self._move_skipped = len(plan.entries) - len(plan.valid_entries)
        self._move_crash = ""
        self._set_moving(True)
        self._show_move_progress(0, len(plan.valid_entries))
        self._thread_pool.start(job)

    def _show_move_progress(self, done: int, total: int) -> None:
        self.status_label.setText(f"Moving {done}/{total}\u2026")

    def _remember_move_crash(self, message: str) -> None:
        self._move_crash = message

    def _finish_move(self, outcomes: list[RelocationOutcome]) -> None:
        self._move_job = None
        self._set_moving(False)
        self._finish_relocation("moved", outcomes, self._move_skipped)
        if self._move_crash:
            self.status_label.setText(f"Move stopped by an unexpected error: {self._move_crash}")
        self.move_finished.emit()

    def _set_moving(self, moving: bool) -> None:
        for widget in self._get_action_widgets():
            widget.setEnabled(not moving)
        self.refresh_preview()

    def _get_action_widgets(self) -> tuple[QWidget, ...]:
        return (
            self.open_folder_button,
            self.session_button,
            self.move_button,
            self.operation_input,
            self.rename_text_input,
            self.table_view,
        )

    def _finish_relocation(
        self, verb: str, outcomes: list[RelocationOutcome], skipped: int
    ) -> None:
        self._session_files = replace_relocated_paths(self._session_files, outcomes)
        listed_files = replace_relocated_paths(self.table_model.get_files(), outcomes)
        self.table_model.set_files(keep_inside(listed_files, self._folder), self._folder)
        self.refresh_preview()
        self.status_label.setText(format_relocation_summary(verb, outcomes, skipped))

    def _reload_files(self) -> None:
        folder = self._folder
        files = self._session_files if folder is None else list_audio_files(folder)
        self.table_model.set_files(files, folder)
        self.source_label.setText(SESSION_LABEL if folder is None else f"Folder: {folder}")
        self.refresh_preview()

    def _get_selected_paths(self) -> list[Path]:
        rows = sorted(index.row() for index in self.table_view.selectionModel().selectedRows())
        return [self.table_model.get_path(row) for row in rows]

    def _make_rule(self) -> RenameRule:
        return self.operation_input.currentData()(self.rename_text_input.text())

    def _build_widgets(self) -> None:
        self.open_folder_button = QPushButton("Open folder…")
        self.session_button = QPushButton("Session downloads")
        self.source_label = QLabel(SESSION_LABEL)
        self.table_model = LibraryTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.operation_input = QComboBox()
        for label, rule in OPERATIONS:
            self.operation_input.addItem(label, rule)
        self.rename_text_input = QLineEdit()
        self.rename_text_input.setPlaceholderText("Text")
        self.apply_button = QPushButton("Rename selected")
        self.apply_button.setEnabled(False)
        self.move_button = QPushButton("Move selected to\u2026")
        self.status_label = QLabel()

    def _build_layout(self) -> None:
        source_row = QHBoxLayout()
        source_row.addWidget(self.open_folder_button)
        source_row.addWidget(self.session_button)
        source_row.addWidget(self.source_label, stretch=1)
        source_row.addWidget(self.move_button)
        rename_row = QHBoxLayout()
        rename_row.addWidget(self.operation_input)
        rename_row.addWidget(self.rename_text_input, stretch=1)
        rename_row.addWidget(self.apply_button)
        layout = QVBoxLayout(self)
        layout.addLayout(source_row)
        layout.addWidget(self.table_view, stretch=1)
        layout.addLayout(rename_row)
        layout.addWidget(self.status_label)

    def _connect_signals(self) -> None:
        self.open_folder_button.clicked.connect(self.open_folder)
        self.session_button.clicked.connect(self.show_session)
        self.table_view.selectionModel().selectionChanged.connect(self.refresh_preview)
        self.operation_input.currentIndexChanged.connect(self.refresh_preview)
        self.rename_text_input.textChanged.connect(self.refresh_preview)
        self.apply_button.clicked.connect(self.apply_rename)
        self.move_button.clicked.connect(self.start_move)
        # Queued: renaming reloads the model, which must not happen inside the editor commit.
        self.table_model.rename_requested.connect(
            self.rename_single_file, Qt.ConnectionType.QueuedConnection
        )
