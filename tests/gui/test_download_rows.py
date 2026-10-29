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
    ItemSkipped,
    LinkStarted,
)
from masterit.download.skip_list import SkipList
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


def make_queued_rows() -> DownloadRows:
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.apply(ItemQueued("a", SONG))
    rows.apply(ItemQueued("a", OTHER))
    return rows


def test_toggling_skip_on_pending_item_requests_skip():
    rows, skip_list = make_queued_rows(), SkipList()
    rows.toggle_skip(1, skip_list)
    assert rows.get_row(1).status == RowStatus.SKIP_REQUESTED
    assert skip_list.is_skipped("a", OTHER.item_id)


def test_toggling_skip_again_restores_pending_item():
    rows, skip_list = make_queued_rows(), SkipList()
    rows.toggle_skip(1, skip_list)
    rows.toggle_skip(1, skip_list)
    assert rows.get_row(1).status == RowStatus.PENDING
    assert not skip_list.is_skipped("a", OTHER.item_id)


def test_pending_link_can_be_skipped():
    rows, skip_list = DownloadRows(), SkipList()
    rows.add_links(["a"])
    rows.toggle_skip(0, skip_list)
    assert skip_list.is_skipped("a", None)


def test_started_rows_cannot_be_skipped():
    rows, skip_list = DownloadRows(), SkipList()
    rows.apply(ItemProgress("a", SONG, 5.0))
    assert not rows.can_toggle_skip(0)
    rows.toggle_skip(0, skip_list)
    assert rows.get_row(0).status == RowStatus.DOWNLOADING
    assert not skip_list.is_skipped("a", SONG.item_id)


def test_only_pending_and_skip_requested_rows_can_toggle():
    rows = make_queued_rows()
    rows.toggle_skip(1, SkipList())
    assert rows.can_toggle_skip(0)
    assert rows.can_toggle_skip(1)


def test_skipped_item_row_is_final():
    rows = make_queued_rows()
    rows.toggle_skip(0, SkipList())
    assert rows.apply(ItemSkipped("a", SONG)) == 0
    assert rows.get_row(0) == DownloadRow("Song", RowStatus.SKIPPED, 0.0, "")
    assert not rows.can_toggle_skip(0)


def test_skipped_link_takes_its_pending_row():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.toggle_skip(0, SkipList())
    assert rows.apply(ItemSkipped("a", None)) == 0
    assert rows.get_row(0) == DownloadRow("a", RowStatus.SKIPPED, 0.0, "")


def test_link_started_before_its_skip_is_replaced_by_its_items():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.toggle_skip(0, SkipList())
    assert rows.apply(ItemQueued("a", SONG)) == 0
    assert get_titles(rows) == ["Song"]


@pytest.mark.parametrize(
    "finish", [DownloadRows.mark_unfinished_cancelled, DownloadRows.mark_pending_failed]
)
def test_skip_requests_left_at_the_end_are_skipped(finish: Any):
    rows = make_queued_rows()
    rows.toggle_skip(0, SkipList())
    finish(rows)
    assert rows.get_row(0).status == RowStatus.SKIPPED


def test_summary_counts_skipped_rows():
    rows = make_queued_rows()
    rows.apply(ItemSkipped("a", SONG))
    assert rows.get_summary().skipped == 1


def test_started_link_cannot_be_skipped():
    rows = DownloadRows()
    rows.add_links(["a"])
    assert rows.apply(LinkStarted("a")) == 0
    assert rows.get_row(0) == DownloadRow("a", RowStatus.STARTED, 0.0, "")
    assert not rows.can_toggle_skip(0)


def test_started_link_is_replaced_by_its_first_item():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.apply(LinkStarted("a"))
    assert rows.apply(ItemQueued("a", SONG)) == 0
    assert get_titles(rows) == ["Song"]


def test_link_started_while_skip_was_requested_is_started():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.toggle_skip(0, SkipList())
    rows.apply(LinkStarted("a"))
    assert rows.get_row(0).status == RowStatus.STARTED


def test_started_link_without_items_fails_at_the_end():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.apply(LinkStarted("a"))
    rows.mark_pending_failed()
    assert rows.get_row(0) == DownloadRow("a", RowStatus.FAILED, 0.0, "Not downloaded")


def test_started_link_is_cancelled():
    rows = DownloadRows()
    rows.add_links(["a"])
    rows.apply(LinkStarted("a"))
    rows.mark_unfinished_cancelled()
    assert rows.get_row(0).status == RowStatus.CANCELLED
