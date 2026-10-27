from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from masterit.gui.library_context import LibraryContext
from masterit.tags.cover_cache import make_cover_cache
from masterit.tags.cover_store import CoverStore
from masterit.tags.tag_store import TagError

COVER_SIZE = 200
NO_COVER = "No cover"
MIXED_COVERS = "<multiple covers>"
UNREADABLE_COVER = "Unreadable cover"


def get_cover_text(digests: set[str | None]) -> str | None:
    """Text replacing the cover, or None when the selection shares one cover."""
    if len(digests) != 1:
        return MIXED_COVERS if digests else ""
    return NO_COVER if None in digests else None


class CoverView(QLabel):
    def __init__(self, context: LibraryContext, store: CoverStore) -> None:
        super().__init__()
        self._context = context
        self._store = store
        self._cache = make_cover_cache(store)
        self._shown_digest: str | None = None
        self.setFixedSize(COVER_SIZE, COVER_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def load_selection(self) -> None:
        paths = self._context.get_selected_paths()
        digests = {self._cache.get(path) for path in paths}
        text = get_cover_text(digests)
        if text is None:
            self._show_cover(paths[0], digests.pop())
        else:
            self._show_text(text)

    def forget(self, paths: Iterable[Path]) -> None:
        self._cache.forget(paths)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _show_text(self, text: str) -> None:
        self._shown_digest = None
        self.setText(text)

    def _show_cover(self, path: Path, digest: str | None) -> None:
        if digest == self._shown_digest:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(self._read_cover(path)):
            self._show_text(UNREADABLE_COVER)
            return
        mode = Qt.TransformationMode.SmoothTransformation
        self.setPixmap(pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, mode))
        self._shown_digest = digest

    def _read_cover(self, path: Path) -> bytes:
        try:
            return self._store.read(path) or b""
        except TagError:
            return b""
