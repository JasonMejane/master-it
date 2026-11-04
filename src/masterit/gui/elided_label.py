from typing import override

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QLabel

MINIMUM_WIDTH = 80


class ElidedLabel(QLabel):
    """Single-line label that shortens long text, like paths, instead of widening its window."""

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setText(text)

    @override
    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text)

    @override
    def minimumSizeHint(self) -> QSize:
        return QSize(MINIMUM_WIDTH, super().minimumSizeHint().height())

    def get_shown_text(self) -> str:
        width = self.contentsRect().width()
        return self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, width)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        alignment = int(self.alignment())
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            alignment,
            self.palette(),
            self.isEnabled(),
            self.get_shown_text(),
            QPalette.ColorRole.WindowText,
        )
