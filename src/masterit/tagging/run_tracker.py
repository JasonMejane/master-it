from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from masterit.tagging.events import (
    FileAutoTagged,
    TaggerEvent,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)


# The reason tells why a file was skipped or failed.
@dataclass(frozen=True)
class AutoTagCell:
    status: str
    reason: str = ""


type Statuses = dict[Path, AutoTagCell]

PENDING = "pending"
STOPPED = "stopped"


def describe_finished(event: TaggingFinished) -> str:
    counts = f"{event.tagged} tagged, {event.skipped} skipped, {event.failed} failed"
    if not event.stopped:
        return f"Auto-tag: {counts}."
    return f"Auto-tag stopped: {counts}, {event.unprocessed} not processed."


class AutoTagRun:
    def __init__(self) -> None:
        self._pending: list[Path] = []
        self.processed: list[Path] = []
        self._total = 0
        self.summary = ""

    @property
    def progress_text(self) -> str:
        return f"Auto-tagging {len(self.processed)}/{self._total}…"

    def add_pending(self, paths: Iterable[Path]) -> Statuses:
        new_paths = list(paths)
        self._pending.extend(new_paths)
        return dict.fromkeys(new_paths, AutoTagCell(PENDING))

    def apply(self, event: TaggerEvent) -> Statuses:
        handlers: dict[type, Callable[[Any], Statuses]] = {
            TaggingStarted: self._start,
            FileAutoTagged: self._record_file,
            TaggingFinished: self._finish_run,
            TaggingFailed: self._fail_run,
        }
        return handlers[type(event)](cast(Any, event))

    def finish(self) -> Statuses:
        processed = set(self.processed)
        unfinished = [path for path in self._pending if path not in processed]
        return dict.fromkeys(unfinished, AutoTagCell(STOPPED))

    def _start(self, event: TaggingStarted) -> Statuses:
        self._total = event.total
        return {}

    def _record_file(self, event: FileAutoTagged) -> Statuses:
        self.processed.append(event.path)
        return {event.path: AutoTagCell(str(event.status), event.reason)}

    def _finish_run(self, event: TaggingFinished) -> Statuses:
        self.summary = describe_finished(event)
        return {}

    def _fail_run(self, event: TaggingFailed) -> Statuses:
        self.summary = f"Auto-tag failed: {event.message}"
        return {}
