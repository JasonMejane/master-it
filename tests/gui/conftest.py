from collections.abc import Iterator

import pytest
from PySide6.QtCore import SIGNAL, Qt
from PySide6.QtWidgets import QApplication

from masterit.gui import theme

SCHEME_CHANGED = SIGNAL("colorSchemeChanged(Qt::ColorScheme)")


@pytest.fixture(autouse=True)
def isolated_app_look(qapp: QApplication) -> Iterator[None]:
    """Keeps a theme applied by one test from styling the next ones."""
    assert not qapp.styleSheet(), "the style name is unreadable under a stylesheet"
    style, palette, tokens = qapp.style().name(), qapp.palette(), theme.ACTIVE_THEME.tokens
    yield
    hints = qapp.styleHints()
    if hints.receivers(SCHEME_CHANGED):
        hints.colorSchemeChanged.disconnect()
    qapp.setStyleSheet("")
    qapp.setStyle(style)
    qapp.setPalette(palette)
    theme.ACTIVE_THEME.tokens = tokens


@pytest.fixture
def dark_theme(qapp: QApplication) -> None:
    theme.apply_theme(qapp, Qt.ColorScheme.Dark)
