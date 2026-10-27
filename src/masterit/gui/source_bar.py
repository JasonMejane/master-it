from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from masterit.gui.library_source import SESSION_LABEL


class SourceBar(QWidget):
    folder_chosen = Signal(Path)
    session_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.open_folder_button = QPushButton("Open folder…")
        self.session_button = QPushButton("Session downloads")
        self.source_label = QLabel(SESSION_LABEL)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.session_button)
        layout.addWidget(self.source_label, stretch=1)
        self.open_folder_button.clicked.connect(self.choose_folder)
        self.session_button.clicked.connect(self.session_requested)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open folder")
        if folder:
            self.folder_chosen.emit(Path(folder))
