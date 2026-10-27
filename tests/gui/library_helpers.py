from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QItemSelectionModel, QThreadPool
from PySide6.QtWidgets import QFileDialog, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.library_panel import LibraryPanel
from masterit.gui.move_action import MoveConfirmation
from masterit.library.relocation import RelocationPlan
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeTagStore


def confirm_always(parent: QWidget, plan: RelocationPlan, folder: Path) -> bool:
    return True


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
) -> LibraryPanel:
    panel = LibraryPanel(
        lambda: download_folder,
        is_downloading,
        QThreadPool(),
        tag_store or FakeTagStore(),
        confirm_move,
    )
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
