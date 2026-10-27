from pytestqt.qtbot import QtBot

from masterit.gui.main_window import make_main_window


def test_main_window_is_titled_masterit(qtbot: QtBot):
    window = make_main_window()
    qtbot.addWidget(window)
    assert window.windowTitle() == "MasterIt"
