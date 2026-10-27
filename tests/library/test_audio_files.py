from pathlib import Path

from masterit.library.audio_files import list_audio_files


def make_files(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_lists_audio_files_recursively_sorted(tmp_path: Path):
    make_files(tmp_path, "b.mp3", "a.FLAC", "list/c.opus", "list/d.m4a", "e.ogg", "f.wav")
    assert list_audio_files(tmp_path) == [
        tmp_path / "a.FLAC",
        tmp_path / "b.mp3",
        tmp_path / "e.ogg",
        tmp_path / "f.wav",
        tmp_path / "list/c.opus",
        tmp_path / "list/d.m4a",
    ]


def test_ignores_other_files_folders_and_hidden_entries(tmp_path: Path):
    make_files(tmp_path, "cover.jpg", "song.webm.part", ".hidden.mp3", ".cache/x.mp3")
    (tmp_path / "folder.mp3").mkdir()
    assert list_audio_files(tmp_path) == []
