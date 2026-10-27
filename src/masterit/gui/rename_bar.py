from pathlib import Path

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget

from masterit.gui.library_context import RelocationContext
from masterit.library.destinations import make_rename_destination
from masterit.library.relocation import (
    RelocationPlan,
    apply_relocation_plan,
    make_relocation_plan,
)
from masterit.library.rename_rules import AddPrefix, AddSuffix, RemoveText, RenameRule, SetName

OPERATIONS = (("Remove text", RemoveText), ("Add prefix", AddPrefix), ("Add suffix", AddSuffix))


def remove_extension(name: str, suffix: str) -> str:
    return name[: -len(suffix)] if name.lower().endswith(suffix.lower()) else name


class RenameBar(QWidget):
    def __init__(self, context: RelocationContext) -> None:
        super().__init__()
        self._context = context
        self._plan = RelocationPlan(())
        self._build_widgets()
        self._build_layout()
        self.operation_input.currentIndexChanged.connect(self.refresh_preview)
        self.rename_text_input.textChanged.connect(self.refresh_preview)
        self.apply_button.clicked.connect(self.apply_rename)

    def refresh_preview(self) -> None:
        self._plan = make_relocation_plan(
            self._context.get_selected_paths(), make_rename_destination(self._make_rule())
        )
        self._context.show_preview(self._plan)
        self.apply_button.setEnabled(bool(self._plan.valid_entries) and not self._context.is_busy)

    def apply_rename(self) -> None:
        if self._context.is_busy:
            return
        skipped = len(self._plan.entries) - len(self._plan.valid_entries)
        self._context.finish_relocation("renamed", apply_relocation_plan(self._plan), skipped)
        self.rename_text_input.clear()

    def rename_single_file(self, path: Path, name: str) -> None:
        # Queued after the editor commit, so a job may have started in between.
        if self._context.is_busy:
            self._context.show_status("Busy: rename ignored.")
            return
        self._rename_single_file(path, name)

    def _rename_single_file(self, path: Path, name: str) -> None:
        plan = make_relocation_plan(
            [path], make_rename_destination(SetName(remove_extension(name, path.suffix)))
        )
        problems = [str(entry.problem) for entry in plan.entries if not entry.is_valid]
        if problems:
            self._context.show_status(problems[0])
            return
        if plan.entries:
            self._context.finish_relocation("renamed", apply_relocation_plan(plan), skipped=0)

    def _make_rule(self) -> RenameRule:
        return self.operation_input.currentData()(self.rename_text_input.text())

    def _build_widgets(self) -> None:
        self.operation_input = QComboBox()
        for label, rule in OPERATIONS:
            self.operation_input.addItem(label, rule)
        self.rename_text_input = QLineEdit()
        self.rename_text_input.setPlaceholderText("Text")
        self.apply_button = QPushButton("Rename selected")
        self.apply_button.setEnabled(False)

    def _build_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.operation_input)
        layout.addWidget(self.rename_text_input, stretch=1)
        layout.addWidget(self.apply_button)
