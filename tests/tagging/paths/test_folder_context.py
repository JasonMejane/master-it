from pathlib import Path

import pytest

from masterit.tagging.paths.folder_context import infer_folder_search_terms
from masterit.tagging.paths.terms import FolderSearchTerms

ROOT = Path("/library")


def infer_from_folders(*folders: str) -> FolderSearchTerms:
    return infer_folder_search_terms(ROOT.joinpath(*folders, "01.mp3"), ROOT)


@pytest.mark.parametrize(
    ("folders", "terms"),
    [
        (("Artist", "2024 - Album", "Disc 1"), FolderSearchTerms("Artist", "Album")),
        (("ACDC - Rock or Bust",), FolderSearchTerms("ACDC", "Rock or Bust")),
        (("Game of Thrones - OST",), FolderSearchTerms(album="Game of Thrones - OST")),
        (("Music", "iTunes Music", "Artiste inconnu", "Album inconnu"), FolderSearchTerms()),
        (("Album",), FolderSearchTerms(album="Album")),
        ((), FolderSearchTerms()),
        (("2024 - ",), FolderSearchTerms()),
        (("_ - Album",), FolderSearchTerms(album="_ - Album")),
        (("_", "Album"), FolderSearchTerms(album="Album")),
        (("Artist", "2024 - "), FolderSearchTerms(artist="Artist")),
        (("Artist - 2020 - Album",), FolderSearchTerms("Artist", "Album")),
        (("Covers", "Vol. 2", "1999-2001"), FolderSearchTerms()),
    ],
)
def test_infers_artist_and_album_from_folders(folders: tuple[str, ...], terms: FolderSearchTerms):
    assert infer_from_folders(*folders) == terms


def test_folders_above_the_source_root_are_not_read():
    source = ROOT / "Artist" / "Album" / "01.mp3"
    assert infer_folder_search_terms(source, ROOT / "Artist") == FolderSearchTerms(album="Album")


def test_collapses_parent_segments_of_the_source_root():
    source = ROOT / "A" / "B" / "x.mp3"
    assert infer_folder_search_terms(source, ROOT / "A" / "..") == FolderSearchTerms("A", "B")


def test_album_markers_end_at_ascii_word_boundaries_only():
    assert infer_from_folders("A - éost") == FolderSearchTerms(album="A - éost")
    assert infer_from_folders("A - Ghostly") == FolderSearchTerms("A", "Ghostly")


def test_word_boundaries_ignore_unicode_case_folding():
    folder = "A - \N{KELVIN SIGN}ost"
    assert infer_from_folders(folder) == FolderSearchTerms(album=folder)
