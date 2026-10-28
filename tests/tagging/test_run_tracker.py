from pathlib import Path

from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)
from masterit.tagging.run_tracker import AutoTagCell, AutoTagRun

SONG_A = Path("/lib/a.mp3")
SONG_B = Path("/lib/b.mp3")


def test_added_files_are_pending():
    run = AutoTagRun()
    assert run.add_pending([SONG_A, SONG_B]) == {
        SONG_A: AutoTagCell("pending"),
        SONG_B: AutoTagCell("pending"),
    }


def test_progress_follows_start_and_file_events():
    run = AutoTagRun()
    assert run.apply(TaggingStarted(2)) == {}
    assert run.progress_text == "Auto-tagging 0/2…"
    assert run.apply(FileAutoTagged(SONG_A, AutoTagStatus.SKIPPED)) == {
        SONG_A: AutoTagCell("skipped")
    }
    assert run.progress_text == "Auto-tagging 1/2…"
    assert run.processed == [SONG_A]


def test_summary_from_finished_event():
    run = AutoTagRun()
    run.apply(TaggingFinished(tagged=2, skipped=1, failed=1, unprocessed=0, stopped=False))
    assert run.summary == "Auto-tag: 2 tagged, 1 skipped, 1 failed."


def test_summary_of_stopped_run_counts_unprocessed():
    run = AutoTagRun()
    run.apply(TaggingFinished(tagged=1, skipped=0, failed=0, unprocessed=3, stopped=True))
    assert run.summary == "Auto-tag stopped: 1 tagged, 0 skipped, 0 failed, 3 not processed."


def test_summary_from_failure_event():
    run = AutoTagRun()
    run.apply(TaggingFailed("Source not found: x"))
    assert run.summary == "Auto-tag failed: Source not found: x"


def test_finish_marks_unprocessed_pending_files_stopped():
    run = AutoTagRun()
    run.add_pending([SONG_A, SONG_B])
    run.apply(FileAutoTagged(SONG_A, AutoTagStatus.TAGGED))
    assert run.finish() == {SONG_B: AutoTagCell("stopped")}


def test_a_file_keeps_the_reason_of_its_status():
    run = AutoTagRun()
    event = FileAutoTagged(SONG_A, AutoTagStatus.FAILED, "Tags not supported for a.wav")
    assert run.apply(event) == {SONG_A: AutoTagCell("failed", "Tags not supported for a.wav")}
