from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QSplitter


def get_splitter_state(splitter: QSplitter) -> QByteArray | None:
    # A splitter never shown has zero sizes, which would restore as a broken layout.
    if not any(splitter.sizes()):
        return None
    return splitter.saveState()
