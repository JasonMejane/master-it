from pathlib import Path

from masterit.gui.library_source import LibrarySource
from masterit.library.relocation import RelocationOutcome

from .library_helpers import make_files


def test_starts_on_empty_session():
    source = LibrarySource()
    assert source.folder is None
    assert source.list_files() == []
    assert source.describe() == "This session's downloads"


def test_download_is_visible_in_session_view():
    source = LibrarySource()
    assert source.add_download(Path("/music/Song.mp3"))
    assert source.list_files() == [Path("/music/Song.mp3")]


def test_download_is_added_once():
    source = LibrarySource()
    source.add_download(Path("/music/Song.mp3"))
    assert not source.add_download(Path("/music/Song.mp3"))
    assert source.list_files() == [Path("/music/Song.mp3")]


def test_download_is_hidden_while_folder_open(tmp_path: Path):
    source = LibrarySource()
    source.open_folder(tmp_path)
    assert not source.add_download(Path("/music/Song.mp3"))
    source.show_session()
    assert source.list_files() == [Path("/music/Song.mp3")]


def test_open_folder_lists_its_audio_files(tmp_path: Path):
    source = LibrarySource()
    make_files(tmp_path, "b.mp3", "list/a.flac", "cover.jpg")
    source.open_folder(tmp_path)
    assert source.list_files() == [tmp_path / "b.mp3", tmp_path / "list/a.flac"]
    assert source.describe() == f"Folder: {tmp_path}"


def test_relocated_session_files_are_tracked():
    source = LibrarySource()
    source.add_download(Path("/music/a.mp3"))
    source.replace_relocated([RelocationOutcome(Path("/music/a.mp3"), Path("/lib/a.mp3"))])
    assert source.list_files() == [Path("/lib/a.mp3")]


def test_session_view_keeps_every_file():
    source = LibrarySource()
    paths = [Path("/music/a.mp3"), Path("/elsewhere/b.mp3")]
    assert source.keep_visible(paths) == paths


def test_folder_view_keeps_only_files_inside(tmp_path: Path):
    source = LibrarySource()
    source.open_folder(tmp_path / "root")
    inside = tmp_path / "root/sub/a.mp3"
    assert source.keep_visible([inside, tmp_path / "out/b.mp3"]) == [inside]
