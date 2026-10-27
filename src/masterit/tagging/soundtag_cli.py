import threading
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

from masterit.cancellation import CancelToken
from masterit.tagging.events import (
    TaggerEvent,
    TaggerEventHandler,
    TaggingFailed,
    TaggingFinished,
    TaggingStopped,
)
from masterit.tagging.soundtag_events import parse_soundtag_event

# Downloads already carry yt-dlp's tags, which SoundTag would otherwise keep.
SOUNDTAG_OPTIONS = ("--json", "--overwrite")
CANCEL_POLL_SECONDS = 0.1


class RunningProcess(Protocol):
    def read_lines(self) -> Iterator[str]: ...

    def interrupt(self) -> None: ...

    def wait(self) -> int: ...

    def read_errors(self) -> str: ...


type ProcessStarter = Callable[[list[str]], RunningProcess]


class SoundTagCliTagger:
    def __init__(self, start_process: ProcessStarter, executable: Path) -> None:
        self._start_process = start_process
        self._executable = executable

    def tag(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        command = [str(self._executable), *SOUNDTAG_OPTIONS, *map(str, paths)]
        process = self._start_process(command)
        finished = threading.Event()
        watcher = threading.Thread(
            target=interrupt_on_cancel, args=(process, cancel_token, finished), daemon=True
        )
        watcher.start()
        try:
            has_ended = relay_events(process.read_lines(), on_event)
            exit_code = process.wait()
        finally:
            finished.set()
            watcher.join()
        if not has_ended:
            on_event(describe_end(exit_code, process.read_errors(), cancel_token))


def describe_end(exit_code: int, errors: str, cancel_token: CancelToken) -> TaggerEvent:
    if cancel_token.is_cancelled:
        return TaggingStopped()
    return TaggingFailed(describe_exit(exit_code, errors))


# Each new request interrupts again: SoundTag quits at once on a second interrupt.
def interrupt_on_cancel(
    process: RunningProcess, cancel_token: CancelToken, finished: threading.Event
) -> None:
    handled = 0
    while not finished.is_set():
        requests = cancel_token.wait_for_request(handled, CANCEL_POLL_SECONDS)
        if requests > handled:
            process.interrupt()
            handled = requests


def relay_events(lines: Iterable[str], on_event: TaggerEventHandler) -> bool:
    has_ended = False
    for line in lines:
        event = parse_soundtag_event(line)
        if event is None:
            continue
        on_event(event)
        has_ended = has_ended or isinstance(event, TaggingFinished | TaggingFailed)
    return has_ended


def describe_exit(exit_code: int, errors: str) -> str:
    error_lines = [line for line in errors.splitlines() if line.strip()]
    return error_lines[-1] if error_lines else f"SoundTag exited with code {exit_code}"
