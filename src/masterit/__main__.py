import os
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from masterit.gui.main_window import make_main_window


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("MasterIt")
    app.setApplicationName("MasterIt")
    window = make_main_window(QSettings())
    window.show()
    exit_code = app.exec()
    if window.download_panel.is_running:
        # Forced quit during a download: its worker thread cannot be interrupted mid-step.
        os._exit(exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
