from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from masterit.gui.elided_label import ElidedLabel

LONG_PATH = "/home/user/" + "very-long-folder-name/" * 10 + "music"


def make_label(qtbot: QtBot, text: str) -> ElidedLabel:
    label = ElidedLabel(text)
    qtbot.addWidget(label)
    return label


def test_label_keeps_the_full_text_and_shows_it_as_tooltip(qtbot: QtBot):
    label = make_label(qtbot, "start")
    label.setText(LONG_PATH)
    assert label.text() == LONG_PATH
    assert label.toolTip() == LONG_PATH


def test_markup_like_paths_are_shown_as_plain_text(qtbot: QtBot):
    assert make_label(qtbot, "/music/<b>").textFormat() == Qt.TextFormat.PlainText


def test_initial_text_is_also_the_tooltip(qtbot: QtBot):
    assert make_label(qtbot, LONG_PATH).toolTip() == LONG_PATH


def test_long_text_does_not_widen_the_minimum_size(qtbot: QtBot):
    short, long = make_label(qtbot, "a"), make_label(qtbot, LONG_PATH)
    assert long.minimumSizeHint().width() == short.minimumSizeHint().width()
    assert long.sizeHint().width() > long.minimumSizeHint().width()


def test_text_is_elided_in_the_middle_when_narrow(qtbot: QtBot):
    label = make_label(qtbot, LONG_PATH)
    label.resize(200, label.sizeHint().height())
    shown = label.get_shown_text()
    assert "…" in shown
    assert shown.startswith("/home/")
    assert shown.endswith("music")


def test_text_is_whole_when_wide_enough(qtbot: QtBot):
    label = make_label(qtbot, LONG_PATH)
    label.resize(label.sizeHint())
    assert label.get_shown_text() == LONG_PATH
