from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QWidget

from masterit.gui.album_dialog import ask_album
from masterit.gui.move_action import MoveConfirmation
from masterit.gui.move_dialog import confirm_move
from masterit.gui.repack_dialog import confirm_repack
from masterit.library.library_layout import AlbumTarget
from masterit.repack.pipeline import RepackPlan
from masterit.tagging.tagger import Tagger
from masterit.tags.cover_store import CoverStore
from masterit.tags.tag_store import TagStore

type AlbumQuestion = Callable[[QWidget, AlbumTarget], AlbumTarget | None]
type RepackConfirmation = Callable[[QWidget, RepackPlan, Path], bool]


class LibraryRootStore(Protocol):
    def load_library_root(self) -> Path | None: ...

    def save_library_root(self, root: Path) -> None: ...


@dataclass(frozen=True)
class LibraryServices:
    get_download_folder: Callable[[], Path]
    is_downloading: Callable[[], bool]
    thread_pool: QThreadPool
    tag_store: TagStore
    cover_store: CoverStore
    root_store: LibraryRootStore
    # Called when a run starts, on the GUI thread, so settings changed meanwhile apply.
    make_tagger: Callable[[], Tagger]
    confirm_move: MoveConfirmation = confirm_move
    ask_album: AlbumQuestion = ask_album
    confirm_repack: RepackConfirmation = confirm_repack
