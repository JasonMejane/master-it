from pathlib import Path

from PySide6.QtCore import Qt
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
from masterit.library.audio_files import list_audio_files
from masterit.library.rename_plan import (
    RenameOutcome,
    RenamePlan,
    apply_rename_plan,
    make_rename_plan,
    replace_renamed_paths,
)
from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText, RenameRule, SetName

OPERATIONS = (("Remove text", RemoveText), ("Add prefix", AddPrefix), ("Add suffix", AddSuffix))
SESSION_LABEL = "This session's downloads"


def remove_extension(name: str, suffix: str) -> str:
    return name[: -len(suffix)] if name.lower().endswith(suffix.lower()) else name


def format_rename_summary(outcomes: list[RenameOutcome], skipped: int) -> str:
    failures = [outcome for outcome in outcomes if not outcome.succeeded]
    summary = f"{len(outcomes) - len(failures)} renamed, {skipped} skipped, {len(failures)} failed."
    if not failures:
        return summary
    return f"{summary} {failures[0].source.name}: {failures[0].error}"


class LibraryPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._session_files: list[Path] = []
        self._folder: Path | None = None
        self._plan = RenamePlan(())
        self._build_widgets()
        self._build_layout()
        self._connect_signals()

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
        self._plan = make_rename_plan(self._get_selected_paths(), self._make_rule())
        self.table_model.set_preview(self._plan)
        self.apply_button.setEnabled(bool(self._plan.valid_entries))

    def apply_rename(self) -> None:
        skipped = len(self._plan.entries) - len(self._plan.valid_entries)
        self._finish_rename(apply_rename_plan(self._plan), skipped)
        self.rename_text_input.clear()

    def rename_single_file(self, path: Path, name: str) -> None:
        plan = make_rename_plan([path], SetName(remove_extension(name, path.suffix)))
        problems = [str(entry.problem) for entry in plan.entries if not entry.is_valid]
        if problems:
            self.status_label.setText(problems[0])
            return
        if plan.entries:
            self._finish_rename(apply_rename_plan(plan), skipped=0)

    def _finish_rename(self, outcomes: list[RenameOutcome], skipped: int) -> None:
        self._session_files = replace_renamed_paths(self._session_files, outcomes)
        listed_files = replace_renamed_paths(self.table_model.get_files(), outcomes)
        self.table_model.set_files(listed_files, self._folder)
        self.refresh_preview()
        self.status_label.setText(format_rename_summary(outcomes, skipped))

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
        self.status_label = QLabel()

    def _build_layout(self) -> None:
        source_row = QHBoxLayout()
        source_row.addWidget(self.open_folder_button)
        source_row.addWidget(self.session_button)
        source_row.addWidget(self.source_label, stretch=1)
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
        # Queued: renaming reloads the model, which must not happen inside the editor commit.
        self.table_model.rename_requested.connect(
            self.rename_single_file, Qt.ConnectionType.QueuedConnection
        )
