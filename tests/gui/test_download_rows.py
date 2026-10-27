from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from masterit.download.events import (
    ItemCompleted,
    ItemFailed,
    ItemProgress,
    ItemQueued,
    ItemRef,
)
from masterit.gui.download_rows import (
    DownloadRow,
    DownloadRows,
    DownloadSummary,
    Placement,
    RowStatus,
)

SONG = ItemRef("id1", "Song")
OTHER = ItemRef("id2", "Other")
PENDING_SONG = DownloadRow("Song", RowStatus.PENDING, 0.0, "")


def get_titles(rows: DownloadRows) -> list[str]:
    return [rows.get_row(index).title for index in range(rows.count)]


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


def test_links_start_as_pending_rows_named_after_url():
    rows = DownloadRows()
    rows.add_links(["a", "b"])
    assert rows.get_row(1) == DownloadRow("b", RowStatus.PENDING, 0.0, "")


def test_first_item_of_a_link_replaces_its_pending_row():
    rows = DownloadRows()
    rows.add_links(["a", "b"])
    assert rows.find_placement(ItemQueued("b", SONG)) == Placement(1, is_new=False)
    assert rows.apply(ItemQueued("b", SONG)) == 1
    assert rows.get_row(1) == PENDING_SONG
    assert rows.apply(ItemProgress("b", SONG, 5.0)) == 1


def test_other_items_of_a_link_are_inserted_after_its_rows():
    rows = DownloadRows()
    rows.add_links(["a", "b"])
    rows.apply(ItemQueued("a", SONG))
    assert rows.find_placement(ItemQueued("a", OTHER)) == Placement(1, is_new=True)
    rows.apply(ItemQueued("a", OTHER))
    assert get_titles(rows) == ["Song", "Other", "b"]
    assert rows.apply(ItemCompleted("b", SONG, Path("/music/Song.mp3"))) == 2


def test_queued_item_does_not_reset_a_started_row():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 30.0))
    rows.apply(ItemQueued("a", SONG))
    assert rows.get_row(0).status == RowStatus.DOWNLOADING


def test_failure_without_item_takes_the_pending_row_of_its_link():
    rows = DownloadRows()
    rows.add_links(["a", "b"])
    assert rows.apply(ItemFailed("a", None, "Unsupported URL")) == 0
    assert rows.get_row(0) == DownloadRow("a", RowStatus.FAILED, 0.0, "Unsupported URL")
    assert rows.apply(ItemFailed("a", None, "again")) == 1
    assert get_titles(rows) == ["a", "a", "b"]


def test_summary_counts_outcomes():
    rows = DownloadRows()
    rows.apply(ItemCompleted("a", SONG, Path("/music/Song.mp3")))
    rows.apply(ItemCompleted("b", SONG, Path("/music/Song.mp3"), ("no cover",)))
    rows.apply(ItemFailed("c", None, "unavailable"))
    rows.apply(ItemProgress("d", SONG, 5.0))
    rows.add_links(["e"])
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
    assert rows.find_placement(progress) == Placement(0, is_new=True)
    rows.apply(progress)
    assert not rows.find_placement(ItemFailed("a", SONG, "boom")).is_new
    assert rows.find_placement(ItemFailed("a", None, "boom")).is_new


@dataclass(frozen=True)
class UnknownEvent:
    source_url: str
    item: ItemRef


def test_unknown_event_is_rejected():
    with pytest.raises(NotImplementedError):
        DownloadRows().apply(cast(Any, UnknownEvent("a", SONG)))


def test_unfinished_rows_are_marked_cancelled():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 40.0))
    rows.apply(ItemCompleted("b", SONG, Path("/music/Song.mp3")))
    rows.add_links(["c"])
    rows.mark_unfinished_cancelled()
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.CANCELLED, 40.0, "")
    assert rows.get_row(1).status == RowStatus.COMPLETED
    assert rows.get_row(2).status == RowStatus.CANCELLED


def test_pending_rows_left_at_the_end_failed():
    rows = DownloadRows()
    rows.apply(ItemProgress("a", SONG, 40.0))
    rows.add_links(["b"])
    rows.mark_pending_failed()
    assert rows.get_row(0).status == RowStatus.DOWNLOADING
    assert rows.get_row(1) == DownloadRow("b", RowStatus.FAILED, 0.0, "Not downloaded")
