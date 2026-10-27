import os
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from typing import IO, Any, Protocol, cast

# Read with defaults so the Windows strategy also loads, and is tested, elsewhere.
WINDOWS_NEW_PROCESS_GROUP: int = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
WINDOWS_CTRL_BREAK: int = getattr(signal, "CTRL_BREAK_EVENT", 1)


class ProcessGroup(Protocol):
    def get_popen_options(self) -> dict[str, Any]: ...

    def interrupt(self, popen: subprocess.Popen[str]) -> None: ...


# SoundTag may run behind a wrapper (Volta shim, npm script) that neither handles nor
# forwards SIGINT, so the interrupt goes to the whole process group.
class PosixProcessGroup:
    def get_popen_options(self) -> dict[str, Any]:
        return {"process_group": 0}

    def interrupt(self, popen: subprocess.Popen[str]) -> None:
        # poll() cannot see an exit while another thread waits, so the group may be gone.
        with suppress(ProcessLookupError):
            os.killpg(popen.pid, signal.SIGINT)


class WindowsProcessGroup:
    def get_popen_options(self) -> dict[str, Any]:
        return {"creationflags": WINDOWS_NEW_PROCESS_GROUP}

    def interrupt(self, popen: subprocess.Popen[str]) -> None:
        popen.send_signal(WINDOWS_CTRL_BREAK)


PROCESS_GROUP: ProcessGroup = WindowsProcessGroup() if os.name == "nt" else PosixProcessGroup()


class SubprocessProcess:
    def __init__(self, popen: subprocess.Popen[str], errors_file: IO[bytes]) -> None:
        self._popen = popen
        self._output = cast(IO[str], popen.stdout)
        self._errors_file = errors_file
        self._errors = ""

    def read_lines(self) -> Iterator[str]:
        yield from self._output

    def interrupt(self) -> None:
        PROCESS_GROUP.interrupt(self._popen)

    def wait(self) -> int:
        exit_code = self._popen.wait()
        self._output.close()
        self._errors_file.seek(0)
        self._errors = self._errors_file.read().decode("utf-8", "replace")
        self._errors_file.close()
        return exit_code

    def read_errors(self) -> str:
        return self._errors


def start_subprocess(command: list[str]) -> SubprocessProcess:
    # A file, not a pipe: an unread stderr pipe could fill up and block SoundTag.
    errors_file = tempfile.TemporaryFile()  # noqa: SIM115 - closed by wait()
    try:
        popen = subprocess.Popen(  # noqa: S603 - executable resolved by the caller
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=errors_file,
            text=True,
            encoding="utf-8",
            errors="replace",
            **PROCESS_GROUP.get_popen_options(),
        )
    except OSError:
        errors_file.close()
        raise
    return SubprocessProcess(popen, errors_file)
