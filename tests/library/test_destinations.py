from pathlib import Path

from masterit.library.destinations import (
    Destination,
    make_move_destination,
    make_rename_destination,
)
from masterit.library.rename_rules import AddPrefix


def test_rename_destination_keeps_folder_and_extension():
    make_destination = make_rename_destination(AddPrefix("X "))
    assert make_destination(Path("/music/Song.mp3")) == Destination(Path("/music"), "X Song.mp3")


def test_move_destination_keeps_file_name():
    make_destination = make_move_destination(Path("/library"))
    assert make_destination(Path("/music/list/Song.mp3")) == Destination(
        Path("/library"), "Song.mp3"
    )


def test_destination_path_joins_folder_and_name():
    assert Destination(Path("/library"), "Song.mp3").path == Path("/library/Song.mp3")
