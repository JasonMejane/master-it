from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.splitter_state import get_splitter_state


def make_splitter(qtbot: QtBot) -> QSplitter:
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(QWidget())
    splitter.addWidget(QWidget())
    qtbot.addWidget(splitter)
    splitter.resize(1000, 400)
    return splitter


def test_never_shown_splitter_has_no_state(qtbot: QtBot):
    assert get_splitter_state(make_splitter(qtbot)) is None


def test_shown_splitter_state_restores_its_sizes(qtbot: QtBot):
    splitter = make_splitter(qtbot)
    splitter.show()
    splitter.setSizes([300, 700])
    state = get_splitter_state(splitter)
    assert state is not None
    restored = make_splitter(qtbot)
    restored.show()
    restored.restoreState(state)
    assert restored.sizes() == splitter.sizes()
