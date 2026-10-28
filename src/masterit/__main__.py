import os
import sys

from masterit.desktop.commands import run_command_line


def main() -> int:
    exit_code = run_command_line(sys.argv, os.environ, sys.stdout)
    return run_app() if exit_code is None else exit_code


# Qt loads only for the app, so desktop options work where its libraries cannot.
def run_app() -> int:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from masterit.gui.app_setup import configure_application
    from masterit.gui.main_window import make_main_window

    app = QApplication(sys.argv)
    configure_application(app)
    window = make_main_window(QSettings())
    window.show()
    exit_code = app.exec()
    if window.download_panel.is_running:
        # Forced quit during a download: its worker thread cannot be interrupted mid-step.
        os._exit(exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
