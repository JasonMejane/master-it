from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, QThreadPool
from PySide6.QtWidgets import QFileDialog, QWidget
from pytestqt.qtbot import QtBot

from masterit.cancellation import CancelToken
from masterit.gui.library_panel import LibraryPanel
from masterit.gui.library_services import LibraryServices
from masterit.gui.move_action import MoveConfirmation
from masterit.library.library_layout import AlbumTarget
from masterit.library.relocation import RelocationPlan
from masterit.repack.pipeline import RepackPlan
from masterit.tagging.events import TaggerEventHandler
from masterit.tagging.tagger import Tagger
from masterit.tags.cover_store import CoverStore
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeCoverStore, FakeTagStore


def confirm_always(parent: QWidget, plan: RelocationPlan, folder: Path) -> bool:
    return True


def ask_jazz_album(parent: QWidget, suggestion: AlbumTarget) -> AlbumTarget:
    return AlbumTarget("Queen", "Jazz")


def confirm_repack_always(parent: QWidget, plan: RepackPlan, root: Path) -> bool:
    return True


class FakeRootStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root

    def load_library_root(self) -> Path | None:
        return self.root

    def save_library_root(self, root: Path) -> None:
        self.root = root


def make_files(root: Path, *names: str) -> list[Path]:
    paths = [root / name for name in names]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    return paths


def make_panel(
    qtbot: QtBot,
    download_folder: Path = Path("/music/YT_DL"),
    confirm_move: MoveConfirmation = confirm_always,
    is_downloading: Callable[[], bool] = lambda: False,
    tag_store: TagStore | None = None,
    tagger: Tagger | None = None,
    root_store: FakeRootStore | None = None,
    cover_store: CoverStore | None = None,
    make_tagger: Callable[[], Tagger] | None = None,
) -> LibraryPanel:
    services = LibraryServices(
        get_download_folder=lambda: download_folder,
        is_downloading=is_downloading,
        thread_pool=QThreadPool(),
        tag_store=tag_store or FakeTagStore(),
        cover_store=cover_store or FakeCoverStore(),
        root_store=root_store or FakeRootStore(),
        make_tagger=make_tagger or (lambda: tagger or UnusedTagger()),
        confirm_move=confirm_move,
        ask_album=ask_jazz_album,
        confirm_repack=confirm_repack_always,
    )
    panel = LibraryPanel(services)
    qtbot.addWidget(panel)
    return panel


def choose(folder: str) -> Callable[..., str]:
    def choose_folder(*args: object) -> str:
        return folder

    return choose_folder


def open_folder(panel: LibraryPanel, folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(folder)))
    panel.source_bar.open_folder_button.click()


def select_rows(panel: LibraryPanel, *rows: int) -> None:
    selection = panel.table_view.selectionModel()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for row in rows:
        selection.select(panel.table_model.index(row, 0), flags)


def get_names(panel: LibraryPanel) -> list[object]:
    model = panel.table_model
    return [model.data(model.index(row, 0)) for row in range(model.rowCount())]


class UnusedTagger:
    def tag(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        raise AssertionError("no tagger expected in this test")
