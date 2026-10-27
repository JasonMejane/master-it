import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEvent,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)

type EventData = dict[str, Any]


def parse_start(data: EventData) -> TaggerEvent:
    return TaggingStarted(int(data["total"]))


def parse_file(data: EventData) -> TaggerEvent:
    return FileAutoTagged(Path(data["path"]), AutoTagStatus(data["status"]))


def parse_summary(data: EventData) -> TaggerEvent:
    return TaggingFinished(
        tagged=int(data["tagged"]),
        skipped=int(data["skipped"]),
        failed=int(data["failed"]),
        unprocessed=int(data["unprocessed"]),
        stopped=bool(data["stopped"]),
    )


def parse_error(data: EventData) -> TaggerEvent:
    return TaggingFailed(str(data["message"]))


PARSERS: dict[str, Callable[[EventData], TaggerEvent]] = {
    "start": parse_start,
    "file": parse_file,
    "summary": parse_summary,
    "error": parse_error,
}


def parse_soundtag_event(line: str) -> TaggerEvent | None:
    data = load_object(line)
    parser = PARSERS.get(str(data.get("type")))
    if parser is None:
        return None
    try:
        return parser(data)
    except KeyError, ValueError, TypeError:
        return None


def load_object(line: str) -> EventData:
    try:
        data: object = json.loads(line)
    except json.JSONDecodeError:
        return {}
    return cast(EventData, data) if isinstance(data, dict) else {}
