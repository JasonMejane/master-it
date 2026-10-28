import threading
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog
from pytestqt.qtbot import QtBot

from masterit.cancellation import CancelToken
from masterit.gui.library_panel import LibraryPanel
from masterit.repack.pipeline import RepackPlan
from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEventHandler,
    TaggingFinished,
    TaggingStarted,
)
from masterit.tags.fields import TagField

from ..tags.fakes import FakeTagStore
from .library_helpers import FakeRootStore, choose, make_files, make_panel, select_rows

AUTO_TAG_COLUMN = 11
GENRE_COLUMN = 8


class FakeTagger:
    def __init__(self, store: FakeTagStore | None = None) -> None:
        self.calls: list[list[Path]] = []
        self.store = store
        self.error: Exception | None = None
        self.wait_for_cancel = False
        self.cancel_requests_needed = 1
        self.started = threading.Event()

    def tag(self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken):
        self.calls.append(paths)
        self.started.set()
        if self.error is not None:
            raise self.error
        run = self._wait_for_cancel if self.wait_for_cancel else self._tag_all
        run(paths, on_event, cancel_token)

    def _wait_for_cancel(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        cancel_token.wait_for_request(self.cancel_requests_needed - 1, 5)
        on_event(TaggingFinished(0, 0, 0, len(paths), stopped=True))

    def _tag_all(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        for path in paths:
            self._write_genre(path)
            on_event(FileAutoTagged(path, AutoTagStatus.TAGGED))
        on_event(TaggingFinished(len(paths), 0, 0, 0, stopped=False))

    def _write_genre(self, path: Path) -> None:
        if self.store is not None:
            self.store.write(path, {TagField.GENRE: "Rock"})


def get_cell(panel: LibraryPanel, row: int, column: int) -> object:
    return panel.table_model.data(panel.table_model.index(row, column))


def make_session_panel(
    qtbot: QtBot, tmp_path: Path, tagger: FakeTagger | None, **options: object
) -> LibraryPanel:
    store = FakeTagStore(
        {tmp_path / "dl" / "song.mp3": {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"}}
    )
    if tagger is not None:
        tagger.store = store
    panel = make_panel(qtbot, tmp_path / "dl", tag_store=store, tagger=tagger, **options)  # pyright: ignore[reportArgumentType]
    for path in make_files(tmp_path / "dl", "song.mp3"):
        panel.add_downloaded_file(path)
    return panel


def test_actions_start_idle_and_need_a_selection(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    panel = make_session_panel(qtbot, tmp_path, tagger)
    action = panel.auto_tag_action
    assert action.auto_tag_button.isEnabled()
    assert not action.cancel_button.isEnabled()
    action.start_auto_tag()
    assert tagger.calls == []
    assert not panel.is_busy


def test_root_label_shows_saved_root(qtbot: QtBot, tmp_path: Path):
    panel = make_session_panel(qtbot, tmp_path, FakeTagger(), root_store=FakeRootStore(tmp_path))
    assert panel.auto_tag_action.root_label.text() == f"Library: {tmp_path}"
    unset = make_session_panel(qtbot, tmp_path, FakeTagger())
    assert unset.auto_tag_action.root_label.text() == "No library root"


def test_root_button_saves_chosen_root(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root_store = FakeRootStore()
    panel = make_session_panel(qtbot, tmp_path, FakeTagger(), root_store=root_store)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "lib")))
    panel.auto_tag_action.root_button.click()
    assert root_store.root == tmp_path / "lib"
    assert panel.auto_tag_action.root_label.text() == f"Library: {tmp_path / 'lib'}"


def test_actions_without_selection_ask_for_it(qtbot: QtBot, tmp_path: Path):
    panel = make_session_panel(qtbot, tmp_path, FakeTagger())
    panel.auto_tag_action.auto_tag_button.click()
    assert panel.status_label.text() == "Select files to auto-tag."
    panel.auto_tag_action.repack_button.click()
    assert panel.status_label.text() == "Select files to repack."


def test_auto_tag_shows_statuses_summary_and_new_tags(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    panel = make_session_panel(qtbot, tmp_path, tagger)
    select_rows(panel, 0)
    assert get_cell(panel, 0, GENRE_COLUMN) == ""
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.auto_tag_action.auto_tag_button.click()
    assert tagger.calls == [[tmp_path / "dl" / "song.mp3"]]
    assert get_cell(panel, 0, AUTO_TAG_COLUMN) == "tagged"
    assert get_cell(panel, 0, GENRE_COLUMN) == "Rock"
    assert panel.status_label.text() == "Auto-tag: 1 tagged, 0 skipped, 0 failed."
    assert not panel.is_busy


def test_builds_a_tagger_for_each_run_with_a_selection(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    builds: list[str] = []
    panel = make_session_panel(
        qtbot, tmp_path, tagger, make_tagger=lambda: builds.append("tagger") or tagger
    )
    panel.auto_tag_action.start_auto_tag()
    select_rows(panel, 0)
    for _ in range(2):
        with qtbot.waitSignal(panel.work_finished, timeout=2000):
            panel.auto_tag_action.auto_tag_button.click()
    assert builds == ["tagger", "tagger"]


def test_repack_moves_into_library_then_tags(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    tagger = FakeTagger()
    panel = make_session_panel(qtbot, tmp_path, tagger, root_store=FakeRootStore(tmp_path / "lib"))
    select_rows(panel, 0)
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.auto_tag_action.repack_button.click()
    target = tmp_path / "lib" / "Queen" / "Queen - Mustapha.mp3"
    assert target.exists()
    assert tagger.calls == [[target]]
    assert panel.table_model.get_path(0) == target
    assert get_cell(panel, 0, AUTO_TAG_COLUMN) == "tagged"
    assert panel.status_label.text() == (
        "1 moved, 0 skipped, 0 failed. Auto-tag: 1 tagged, 0 skipped, 0 failed."
    )


def test_repack_without_root_asks_for_one(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root_store = FakeRootStore()
    panel = make_session_panel(qtbot, tmp_path, FakeTagger(), root_store=root_store)
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(""))
    panel.auto_tag_action.repack_button.click()
    assert not panel.is_busy
    assert root_store.root is None
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "lib")))
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.auto_tag_action.repack_button.click()
    assert root_store.root == tmp_path / "lib"


def test_declined_repack_changes_nothing(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    builds: list[str] = []
    panel = make_session_panel(
        qtbot,
        tmp_path,
        tagger,
        root_store=FakeRootStore(tmp_path / "lib"),
        make_tagger=lambda: builds.append("tagger") or tagger,
    )
    plans: list[RepackPlan] = []

    def decline(parent: object, plan: RepackPlan, root: Path) -> bool:
        plans.append(plan)
        return False

    panel.auto_tag_action.confirm_repack = decline
    select_rows(panel, 0)
    panel.auto_tag_action.repack_button.click()
    assert len(plans[0].moves.valid_entries) == 1
    assert tagger.calls == []
    assert builds == []
    assert (tmp_path / "dl" / "song.mp3").exists()


def test_cancel_stops_auto_tag_and_marks_unprocessed_files(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.wait_for_cancel = True
    panel = make_session_panel(qtbot, tmp_path, tagger)
    select_rows(panel, 0)
    action = panel.auto_tag_action
    action.auto_tag_button.click()
    try:
        assert tagger.started.wait(2)
        assert panel.is_busy
        assert action.cancel_button.isEnabled()
        assert not action.auto_tag_button.isEnabled()
        assert not panel.move_action.isEnabled()
        assert not panel.table_view.isEnabled()
        assert get_cell(panel, 0, AUTO_TAG_COLUMN) == "pending"
    finally:
        with qtbot.waitSignal(panel.work_finished, timeout=2000):
            action.cancel_button.click()
            assert panel.status_label.text() == (
                "Stopping after the current file… (Stop now abandons it)"
            )
            assert action.cancel_button.text() == "Stop now"
    assert get_cell(panel, 0, AUTO_TAG_COLUMN) == "stopped"
    assert panel.status_label.text() == (
        "Auto-tag stopped: 0 tagged, 0 skipped, 0 failed, 1 not processed."
    )
    assert not action.cancel_button.isEnabled()
    assert action.cancel_button.text() == "Cancel"
    assert action.auto_tag_button.isEnabled()


def test_second_press_stops_at_once(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.wait_for_cancel = True
    tagger.cancel_requests_needed = 2
    panel = make_session_panel(qtbot, tmp_path, tagger)
    select_rows(panel, 0)
    action = panel.auto_tag_action
    action.auto_tag_button.click()
    assert tagger.started.wait(2)
    action.cancel_button.click()
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        action.cancel_button.click()
        assert panel.status_label.text() == "Stopping now…"
        assert not action.cancel_button.isEnabled()
        action.set_busy(True)
        assert not action.cancel_button.isEnabled()


def test_progress_keeps_the_stopping_notice(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    panel = make_session_panel(qtbot, tmp_path, tagger)
    action = panel.auto_tag_action
    select_rows(panel, 0)
    tagger.wait_for_cancel = True
    action.auto_tag_button.click()
    assert tagger.started.wait(2)
    action.cancel_button.click()
    action.handle_event(TaggingStarted(3))
    assert panel.status_label.text() == "Auto-tagging 0/3… Stopping after the current file."
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        action.cancel_button.click()


def test_stop_work_cancels_auto_tag(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.wait_for_cancel = True
    panel = make_session_panel(qtbot, tmp_path, tagger)
    select_rows(panel, 0)
    panel.auto_tag_action.auto_tag_button.click()
    assert tagger.started.wait(2)
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.stop_work()


def test_auto_tag_buttons_are_locked_while_moving(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    panel = make_session_panel(qtbot, tmp_path, FakeTagger())
    select_rows(panel, 0)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", choose(str(tmp_path / "dest")))
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.move_action.move_button.click()
        assert not panel.auto_tag_action.auto_tag_button.isEnabled()
    assert panel.auto_tag_action.auto_tag_button.isEnabled()


def test_unexpected_error_is_reported(qtbot: QtBot, tmp_path: Path):
    tagger = FakeTagger()
    tagger.error = RuntimeError("boom")
    panel = make_session_panel(qtbot, tmp_path, tagger)
    select_rows(panel, 0)
    with qtbot.waitSignal(panel.work_finished, timeout=2000):
        panel.auto_tag_action.auto_tag_button.click()
    assert panel.status_label.text() == "Auto-tag stopped by an unexpected error: boom"
    assert get_cell(panel, 0, AUTO_TAG_COLUMN) == "stopped"
