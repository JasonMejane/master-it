from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from masterit.library.relocation import Relocation, RelocationPlan


def format_move_line(entry: Relocation) -> str:
    if entry.problem is None:
        return entry.source.name
    return f"{entry.source.name} — skipped: {entry.problem}"


def format_move_summary(plan: RelocationPlan, folder: Path) -> str:
    valid_count = len(plan.valid_entries)
    if not valid_count:
        return f"Nothing can be moved to {folder}."
    skipped_count = len(plan.entries) - valid_count
    skipped = f" {skipped_count} will be skipped." if skipped_count else ""
    return f"Move {valid_count} file(s) to {folder}?{skipped}"


class MoveDialog(QDialog):
    def __init__(self, plan: RelocationPlan, folder: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move files")
        self.summary_label = QLabel(format_move_summary(plan, folder))
        self.details = QPlainTextEdit("\n".join(format_move_line(entry) for entry in plan.entries))
        self.details.setReadOnly(True)
        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttons = QDialogButtonBox(buttons)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(plan.valid_entries))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.details)
        layout.addWidget(self.buttons)


def confirm_move(parent: QWidget, plan: RelocationPlan, folder: Path) -> bool:
    return MoveDialog(plan, folder, parent).exec() == QDialog.DialogCode.Accepted
