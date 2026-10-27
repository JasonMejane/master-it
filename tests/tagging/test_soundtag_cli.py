import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from masterit.cancellation import CancelToken
from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEvent,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
    TaggingStopped,
)
from masterit.tagging.soundtag_cli import SoundTagCliTagger

SONG = Path("/music/Queen/Queen - Mustapha.mp3")
SUMMARY = '{"type":"summary","tagged":1,"skipped":0,"failed":0,"unprocessed":0,"stopped":false}'


class FakeProcess:
    def __init__(self, lines: list[str], exit_code: int = 0, errors: str = "") -> None:
        self.lines = lines
        self.exit_code = exit_code
        self.errors = errors
        self.interrupted = threading.Event()

    def read_lines(self) -> Iterator[str]:
        yield from self.lines

    def interrupt(self) -> None:
        self.interrupted.set()

    def wait(self) -> int:
        return self.exit_code

    def read_errors(self) -> str:
        return self.errors


class FakeStarter:
    def __init__(self, process: FakeProcess) -> None:
        self.process = process
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> FakeProcess:
        self.commands.append(command)
        return self.process


def run_tagger(process: FakeProcess, token: CancelToken | None = None) -> list[TaggerEvent]:
    events: list[TaggerEvent] = []
    tagger = SoundTagCliTagger(FakeStarter(process), Path("/bin/soundtag"))
    tagger.tag([SONG], events.append, token or CancelToken())
    return events


def test_runs_soundtag_with_json_overwrite_and_files():
    starter = FakeStarter(FakeProcess([SUMMARY]))
    tagger = SoundTagCliTagger(starter, Path("/bin/soundtag"))
    tagger.tag([SONG, Path("/music/b.opus")], lambda event: None, CancelToken())
    assert starter.commands == [
        ["/bin/soundtag", "--json", "--overwrite", str(SONG), "/music/b.opus"]
    ]


def test_relays_parsed_events_and_ignores_other_lines():
    lines = [
        '{"type":"start","total":1}',
        "not json",
        f'{{"type":"file","path":"{SONG}","status":"tagged"}}',
        SUMMARY,
    ]
    assert run_tagger(FakeProcess(lines)) == [
        TaggingStarted(1),
        FileAutoTagged(SONG, AutoTagStatus.TAGGED),
        TaggingFinished(tagged=1, skipped=0, failed=0, unprocessed=0, stopped=False),
    ]


def test_error_event_is_relayed_without_extra_failure():
    lines = ['{"type":"error","message":"Source not found: x"}']
    assert run_tagger(FakeProcess(lines, exit_code=1)) == [TaggingFailed("Source not found: x")]


def test_exit_without_summary_reports_last_error_line():
    process = FakeProcess([], exit_code=1, errors="Loading\nError: Unknown option: --json\n")
    assert run_tagger(process) == [TaggingFailed("Error: Unknown option: --json")]


def test_exit_without_summary_or_errors_reports_exit_code():
    assert run_tagger(FakeProcess([], exit_code=3)) == [
        TaggingFailed("SoundTag exited with code 3")
    ]


def test_cancel_interrupts_soundtag():
    process = FakeProcess([SUMMARY])
    blocked_lines = threading.Event()

    def read_until_interrupted() -> Iterator[str]:
        blocked_lines.set()
        process.interrupted.wait(5)
        yield SUMMARY

    process.read_lines = read_until_interrupted
    token = CancelToken()
    events: list[TaggerEvent] = []
    tagger = SoundTagCliTagger(FakeStarter(process), Path("/bin/soundtag"))
    worker = threading.Thread(target=tagger.tag, args=([SONG], events.append, token))
    worker.start()
    blocked_lines.wait(5)
    token.cancel()
    worker.join(5)
    assert process.interrupted.is_set()
    assert not worker.is_alive()


def test_finished_run_is_not_interrupted():
    process = FakeProcess([SUMMARY])
    run_tagger(process)
    assert not process.interrupted.is_set()


def test_second_cancel_interrupts_again():
    process = FakeProcess([SUMMARY])
    interrupts: list[int] = []
    process.interrupt = lambda: interrupts.append(1)
    token = CancelToken()
    blocked = threading.Event()
    release = threading.Event()

    def read_until_released() -> Iterator[str]:
        blocked.set()
        release.wait(5)
        yield SUMMARY

    process.read_lines = read_until_released
    tagger = SoundTagCliTagger(FakeStarter(process), Path("/bin/soundtag"))
    worker = threading.Thread(target=tagger.tag, args=([SONG], ignore_event, token))
    worker.start()
    blocked.wait(5)
    token.cancel()
    wait_until(lambda: len(interrupts) == 1)
    token.cancel()
    wait_until(lambda: len(interrupts) == 2)
    release.set()
    worker.join(5)


def ignore_event(event: TaggerEvent) -> None:
    pass


def wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


def test_cancelled_run_without_summary_is_stopped_not_failed():
    token = CancelToken()
    token.cancel()
    assert run_tagger(FakeProcess([], exit_code=-2), token) == [TaggingStopped()]
