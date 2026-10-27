import sys
import tempfile
import time
from typing import IO

import pytest

from masterit.tagging import subprocess_process
from masterit.tagging.subprocess_process import (
    WINDOWS_CTRL_BREAK,
    WINDOWS_NEW_PROCESS_GROUP,
    WindowsProcessGroup,
    start_subprocess,
)

SCRIPT_PREFIX = [sys.executable, "-c"]


def test_reads_stdout_lines_errors_and_exit_code():
    script = "import sys; print('one'); print('two'); sys.stderr.write('oops\\n'); sys.exit(2)"
    process = start_subprocess([*SCRIPT_PREFIX, script])
    assert list(process.read_lines()) == ["one\n", "two\n"]
    assert process.wait() == 2
    assert process.read_errors() == "oops\n"


def test_reads_utf8_output():
    process = start_subprocess(
        [*SCRIPT_PREFIX, "import sys; sys.stdout.buffer.write('é\\n'.encode())"]
    )
    assert list(process.read_lines()) == ["é\n"]
    assert process.wait() == 0


def test_interrupt_stops_a_running_process():
    script = "import time; print('ready', flush=True); time.sleep(30)"
    process = start_subprocess([*SCRIPT_PREFIX, script])
    lines = process.read_lines()
    assert next(lines) == "ready\n"
    started = time.monotonic()
    process.interrupt()
    assert process.wait() != 0
    assert time.monotonic() - started < 10


WRAPPER = """
import signal, subprocess, sys
signal.signal(signal.SIGINT, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, "-c", sys.argv[1]])
sys.exit(child.wait())
"""
# Like node, the child installs its own SIGINT handler over the inherited "ignore".
CHILD = (
    "import signal, time; signal.signal(signal.SIGINT, signal.default_int_handler);"
    " print('ready', flush=True); time.sleep(30)"
)


def test_interrupt_reaches_the_child_of_a_wrapper_ignoring_it():
    process = start_subprocess([*SCRIPT_PREFIX, WRAPPER, CHILD])
    lines = process.read_lines()
    assert next(lines) == "ready\n"
    started = time.monotonic()
    process.interrupt()
    assert process.wait() != 0
    assert time.monotonic() - started < 10


class RecordingPopen:
    def __init__(self) -> None:
        self.signals: list[int] = []

    def send_signal(self, sent: int) -> None:
        self.signals.append(sent)


def test_windows_group_starts_new_group_and_sends_ctrl_break():
    group = WindowsProcessGroup()
    popen = RecordingPopen()
    group.interrupt(popen)  # pyright: ignore[reportArgumentType]
    assert popen.signals == [WINDOWS_CTRL_BREAK]
    assert group.get_popen_options() == {"creationflags": WINDOWS_NEW_PROCESS_GROUP}


def test_failed_start_closes_the_error_file(monkeypatch: pytest.MonkeyPatch):
    opened: list[IO[bytes]] = []
    original = tempfile.TemporaryFile

    def record_file() -> IO[bytes]:
        error_file = original()
        opened.append(error_file)
        return error_file

    monkeypatch.setattr(subprocess_process.tempfile, "TemporaryFile", record_file)
    with pytest.raises(FileNotFoundError):
        start_subprocess(["/definitely/missing/soundtag"])
    assert opened[0].closed


def test_interrupt_after_exit_is_harmless():
    process = start_subprocess([*SCRIPT_PREFIX, "pass"])
    assert process.wait() == 0
    process.interrupt()


def test_interrupt_ignores_a_group_already_gone(monkeypatch: pytest.MonkeyPatch):
    def raise_gone(pid: int, sent: int) -> None:
        raise ProcessLookupError

    process = start_subprocess([*SCRIPT_PREFIX, "import time; time.sleep(30)"])
    monkeypatch.setattr(subprocess_process.os, "killpg", raise_gone)
    process.interrupt()
    monkeypatch.undo()
    process.interrupt()
    assert process.wait() != 0
