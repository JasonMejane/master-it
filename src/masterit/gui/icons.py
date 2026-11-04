from importlib.resources import files
from typing import override

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QIconEngine, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer
from shiboken6 import Shiboken

# PySide frees a clone() result unless Python keeps it; Qt deletes it later, invalidating it.
cloned_engines: list[QIconEngine] = []
ICONS_FOLDER = files("masterit.gui").joinpath("icons")
ICON_NAMES = tuple(
    sorted(item.name[:-4] for item in ICONS_FOLDER.iterdir() if item.name.endswith(".svg"))
)


def get_icon_color(role: QPalette.ColorRole, mode: QIcon.Mode) -> str:
    palette = QGuiApplication.palette()
    if mode == QIcon.Mode.Disabled:
        return palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText).name()
    if mode == QIcon.Mode.Selected:
        return palette.color(QPalette.ColorRole.HighlightedText).name()
    return palette.color(role).name()


def keep_cloned_engine(engine: QIconEngine) -> None:
    cloned_engines[:] = [kept for kept in cloned_engines if Shiboken.isValid(kept)]
    cloned_engines.append(engine)


class PaletteIconEngine(QIconEngine):
    """Draws an SVG in the current palette color, so icons follow theme changes."""

    def __init__(self, svg: str, role: QPalette.ColorRole) -> None:
        super().__init__()
        self._svg = svg
        self._role = role

    @override
    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        svg = self._svg.replace("currentColor", get_icon_color(self._role, mode))
        renderer = QSvgRenderer(QByteArray(svg.encode()))
        renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        # A wider size keeps the glyph in its leading square: the rest is a gap before text.
        side = min(rect.width(), rect.height())
        top = rect.y() + (rect.height() - side) / 2
        renderer.render(painter, QRectF(rect.x(), top, side, side))

    @override
    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        pixmap = QPixmap(size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pixmap

    @override
    def clone(self) -> QIconEngine:
        engine = PaletteIconEngine(self._svg, self._role)
        keep_cloned_engine(engine)
        return engine


def get_icon(name: str, role: QPalette.ColorRole = QPalette.ColorRole.ButtonText) -> QIcon:
    svg = ICONS_FOLDER.joinpath(f"{name}.svg").read_text(encoding="utf-8")
    return QIcon(PaletteIconEngine(svg, role))
