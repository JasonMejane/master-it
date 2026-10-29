from collections.abc import Iterable
from pathlib import Path
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy

from masterit.gui.library_context import LibraryContext
from masterit.tags.cover_cache import make_cover_cache
from masterit.tags.cover_store import CoverStore
from masterit.tags.tag_store import TagError

COVER_SIZE = 200
COVER_MAX_SIZE = 400
NO_COVER = "No cover"
MIXED_COVERS = "<multiple covers>"
UNREADABLE_COVER = "Unreadable cover"
SCALING = (Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


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
        self._cover = QPixmap()
        self.setMinimumSize(COVER_SIZE, COVER_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setMaximumHeight(min(self.width(), COVER_MAX_SIZE))
        if not self._cover.isNull():
            self._show_scaled_cover()

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
        self._cover = QPixmap()
        self.setText(text)

    def _show_cover(self, path: Path, digest: str | None) -> None:
        if digest == self._shown_digest:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(self._read_cover(path)):
            self._show_text(UNREADABLE_COVER)
            return
        self._cover = pixmap.scaled(COVER_MAX_SIZE, COVER_MAX_SIZE, *SCALING)
        self._shown_digest = digest
        self._show_scaled_cover()

    def _show_scaled_cover(self) -> None:
        self.setPixmap(self._cover.scaled(self.size(), *SCALING))

    def _read_cover(self, path: Path) -> bytes:
        try:
            return self._store.read(path) or b""
        except TagError:
            return b""
