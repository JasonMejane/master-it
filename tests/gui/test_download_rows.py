from pathlib import Path
from typing import Any, cast

import pytest

from masterit.download.events import ItemCompleted, ItemFailed, ItemProgress, ItemRef
from masterit.gui.download_rows import DownloadRow, DownloadRows, DownloadSummary, RowStatus

SONG = ItemRef("id1", "Song")


def test_progress_adds_downloading_row():
    rows = DownloadRows()
    assert rows.apply(ItemProgress("a", SONG, 42.0)) == 0
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.DOWNLOADING, 42.0, "")


def test_events_of_same_item_update_its_row():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", ItemRef("id1", "Song (Official Video)"), 10.0))
    assert rows.apply(ItemCompleted("a", SONG, Path("/music/Song.mp3"))) == 0
    assert rows.count == 1
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.COMPLETED, 100.0, "/music/Song.mp3")


def test_same_item_id_from_other_url_gets_own_row():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 10.0))
    assert rows.apply(ItemProgress("b", SONG, 10.0)) == 1


def test_completion_with_warnings_is_flagged():
    rows = DownloadRows()
    rows.apply(ItemCompleted("a", SONG, Path("/music/Song.mp3"), ("no cover", "no tags")))
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.WARNING, 100.0, "no cover; no tags")


def test_failed_item_keeps_its_progress():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 30.0))
    rows.apply(ItemFailed("a", SONG, "network down"))
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.FAILED, 30.0, "network down")


def test_failures_without_item_each_get_a_row_named_after_url():
    rows = DownloadRows()
    rows.apply(ItemFailed("a", None, "unavailable"))
    assert rows.apply(ItemFailed("a", None, "private")) == 1
    assert rows.get_row(1) == DownloadRow("a", RowStatus.FAILED, 0.0, "private")


def test_summary_counts_outcomes():
    rows = DownloadRows()
    rows.apply(ItemCompleted("a", SONG, Path("/music/Song.mp3")))
    rows.apply(ItemCompleted("b", SONG, Path("/music/Song.mp3"), ("no cover",)))
    rows.apply(ItemFailed("c", None, "unavailable"))
    rows.apply(ItemProgress("d", SONG, 5.0))
    assert rows.get_summary() == DownloadSummary(completed=2, with_warnings=1, failed=1)


def test_clear_removes_rows():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 5.0))
    rows.clear()
    assert rows.count == 0
    assert rows.apply(ItemProgress("a", SONG, 5.0)) == 0


def test_new_row_is_detected_before_applying():
    rows = DownloadRows()
    progress = ItemProgress("a", SONG, 5.0)
    assert rows.is_new_row(progress)
    rows.apply(progress)
    assert not rows.is_new_row(ItemFailed("a", SONG, "boom"))
    assert rows.is_new_row(ItemFailed("a", None, "boom"))


def test_unknown_event_is_rejected():
    with pytest.raises(NotImplementedError):
        DownloadRows().apply(cast(Any, "not an event"))


def test_unfinished_rows_are_marked_cancelled():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 40.0))
    rows.apply(ItemCompleted("b", SONG, Path("/music/Song.mp3")))
    rows.mark_unfinished_cancelled()
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.CANCELLED, 40.0, "")
    assert rows.get_row(1).status == RowStatus.COMPLETED
