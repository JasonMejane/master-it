import sys

from PySide6.QtWidgets import QApplication

from masterit.gui.main_window import make_main_window


def main() -> int:
    app = QApplication(sys.argv)
    window = make_main_window()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
