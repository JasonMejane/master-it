from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from masterit.library.library_layout import AlbumTarget
from masterit.repack.pipeline import find_album_problem


class AlbumDialog(QDialog):
    def __init__(self, suggestion: AlbumTarget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Repack album")
        self.artist_edit = QLineEdit(suggestion.artist)
        self.album_edit = QLineEdit(suggestion.album)
        self.problem_label = QLabel()
        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        self.buttons = QDialogButtonBox(buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.artist_edit.textChanged.connect(self._update_ok_button)
        self.album_edit.textChanged.connect(self._update_ok_button)
        self._build_layout()
        self._update_ok_button()

    @property
    def target(self) -> AlbumTarget:
        return AlbumTarget(self.artist_edit.text().strip(), self.album_edit.text().strip())

    def _update_ok_button(self) -> None:
        problem = find_album_problem(self.target)
        self.problem_label.setText(problem)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not problem)

    def _build_layout(self) -> None:
        fields = QFormLayout()
        fields.addRow("Artist", self.artist_edit)
        fields.addRow("Album", self.album_edit)
        layout = QVBoxLayout(self)
        layout.addLayout(fields)
        layout.addWidget(self.problem_label)
        layout.addWidget(self.buttons)


def ask_album(parent: QWidget, suggestion: AlbumTarget) -> AlbumTarget | None:
    dialog = AlbumDialog(suggestion, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.target
