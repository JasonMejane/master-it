from collections.abc import Iterator

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from masterit.gui.app_setup import configure_application
from masterit.gui.theme import get_theme_tokens, make_stylesheet


@pytest.fixture
def restored_app(qapp: QApplication) -> Iterator[QApplication]:
    names = (qapp.organizationName(), qapp.applicationName(), qapp.desktopFileName())
    icon = qapp.windowIcon()
    yield qapp
    qapp.setOrganizationName(names[0])
    qapp.setApplicationName(names[1])
    QGuiApplication.setDesktopFileName(names[2])
    qapp.setWindowIcon(icon)


def test_application_is_named_after_its_desktop_entry(restored_app: QApplication):
    configure_application(restored_app)
    assert restored_app.organizationName() == "MasterIt"
    assert restored_app.applicationName() == "MasterIt"
    assert restored_app.desktopFileName() == "masterit"
    assert not restored_app.windowIcon().isNull()


def test_application_gets_the_app_theme(restored_app: QApplication):
    restored_app.setStyle("Windows")
    configure_application(restored_app)
    scheme = restored_app.styleHints().colorScheme()
    assert restored_app.styleSheet() == make_stylesheet(get_theme_tokens(scheme))
    restored_app.setStyleSheet("")
    assert restored_app.style().name() == "fusion"
