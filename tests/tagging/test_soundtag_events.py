from pathlib import Path

import pytest

from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)
from masterit.tagging.soundtag_events import parse_soundtag_event


def test_start_event_gives_total():
    assert parse_soundtag_event('{"type":"start","total":3}') == TaggingStarted(3)


@pytest.mark.parametrize("status", list(AutoTagStatus))
def test_file_event_gives_path_and_status(status: AutoTagStatus):
    line = f'{{"type":"file","path":"/music/a.mp3","status":"{status}"}}'
    assert parse_soundtag_event(line) == FileAutoTagged(Path("/music/a.mp3"), status)


def test_summary_event_gives_counts():
    line = '{"type":"summary","tagged":1,"skipped":2,"failed":3,"unprocessed":4,"stopped":true}\n'
    assert parse_soundtag_event(line) == TaggingFinished(
        tagged=1, skipped=2, failed=3, unprocessed=4, stopped=True
    )


def test_error_event_gives_message():
    line = '{"type":"error","message":"Source not found: x"}'
    assert parse_soundtag_event(line) == TaggingFailed("Source not found: x")


@pytest.mark.parametrize(
    "line",
    [
        "",
        "PROCESSING COMPLETE",
        "[1, 2]",
        '{"type":"progress"}',
        '{"type":"file","path":"/a.mp3","status":"renamed"}',
        '{"type":"start"}',
    ],
)
def test_unknown_or_malformed_lines_are_ignored(line: str):
    assert parse_soundtag_event(line) is None
