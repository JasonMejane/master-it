from pathlib import Path

from masterit.library.audio_files import list_audio_files
from masterit.library.relocation import RelocationOutcome, replace_relocated_paths

SESSION_LABEL = "This session's downloads"


class LibrarySource:
    def __init__(self) -> None:
        self._session_files: list[Path] = []
        self.folder: Path | None = None

    def add_download(self, path: Path) -> bool:
        if path in self._session_files:
            return False
        self._session_files.append(path)
        return self.folder is None

    def open_folder(self, folder: Path) -> None:
        self.folder = folder

    def show_session(self) -> None:
        self.folder = None

    def list_files(self) -> list[Path]:
        return list(self._session_files) if self.folder is None else list_audio_files(self.folder)

    def describe(self) -> str:
        return SESSION_LABEL if self.folder is None else f"Folder: {self.folder}"

    def replace_relocated(self, outcomes: list[RelocationOutcome]) -> None:
        self._session_files = replace_relocated_paths(self._session_files, outcomes)

    def keep_visible(self, paths: list[Path]) -> list[Path]:
        if self.folder is None:
            return paths
        root = self.folder.resolve()
        return [path for path in paths if path.parent.resolve().is_relative_to(root)]
