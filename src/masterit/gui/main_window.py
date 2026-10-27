from PySide6.QtWidgets import QMainWindow


def make_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("MasterIt")
    return window
