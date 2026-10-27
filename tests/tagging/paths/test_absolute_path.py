from pathlib import Path, PureWindowsPath

from masterit.tagging.paths.absolute_path import get_relative_folders, make_absolute


def test_absolute_paths_collapse_parent_segments_without_resolving_links():
    assert make_absolute(Path("/library/a/../b")) == Path("/library/b")


def test_relative_folders_can_walk_up():
    assert get_relative_folders(Path("/l/A/B"), Path("/l/C")) == ("..", "A", "B")


def test_files_on_another_drive_keep_their_own_folders():
    folder = PureWindowsPath("D:/Artist/Album")
    assert get_relative_folders(folder, PureWindowsPath("C:/library")) == ("Artist", "Album")
    assert get_relative_folders(folder, PureWindowsPath("D:/Artist")) == ("Album",)
