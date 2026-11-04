from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from masterit.desktop.entry import APP_ID, get_icon_path
from masterit.gui.theme import follow_system_theme


def configure_application(app: QApplication) -> None:
    app.setOrganizationName("MasterIt")
    app.setApplicationName("MasterIt")
    # Lets desktops match the window to the installed entry and its icon.
    QGuiApplication.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon(str(get_icon_path())))
    # The stylesheet is tuned for Fusion; desktop styles would mix with it unevenly.
    app.setStyle("Fusion")
    follow_system_theme(app)
