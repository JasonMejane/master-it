from pathlib import Path

import pytest

from masterit.tagging.paths.library_path import infer_library_folder_terms, parse_library_path
from masterit.tagging.paths.terms import FolderSearchTerms, LibraryPathTerms

ROOT = Path("/library")


def parse_in(*parts: str) -> LibraryPathTerms | None:
    return parse_library_path(ROOT.joinpath(*parts))


def get_album_in(*parts: str) -> str:
    terms = parse_in(*parts)
    assert terms is not None
    return terms.album


@pytest.mark.parametrize(
    ("parts", "terms"),
    [
        (
            ("Daft Punk", "Daft Punk - One More Time.mp3"),
            LibraryPathTerms("One More Time", "Daft Punk", ""),
        ),
        (
            ("Queen", "Queen - Greatest Hits", "Queen - Bohemian Rhapsody.flac"),
            LibraryPathTerms("Bohemian Rhapsody", "Queen", "Greatest Hits"),
        ),
        (
            ("Daft Punk - Discovery", "Daft Punk - Digital Love.mp3"),
            LibraryPathTerms("Digital Love", "Daft Punk", "Discovery"),
        ),
        (
            ("Daft Punk - 2001 - Discovery", "CD1", "03 - Daft Punk - Digital Love.mp3"),
            LibraryPathTerms("Digital Love", "Daft Punk", "Discovery"),
        ),
        (("AC_DC", "ac_dc - Thunderstruck.mp3"), LibraryPathTerms("Thunderstruck", "ac dc", "")),
        (
            ("Queen - Innuendo", "Queen - Innuendo - 01 - Bicycle.mp3"),
            LibraryPathTerms("Bicycle", "Queen", "Innuendo"),
        ),
        (("Queen", "Queen - 07 - Bicycle.mp3"), LibraryPathTerms("Bicycle", "Queen", "")),
        (("Queen", "Singles", "Queen - Bicycle.mp3"), LibraryPathTerms("Bicycle", "Queen", "")),
        (("Queen", "Queen - 99 Luftballons.mp3"), LibraryPathTerms("99 Luftballons", "Queen", "")),
    ],
)
def test_reads_library_paths(parts: tuple[str, ...], terms: LibraryPathTerms):
    assert parse_in(*parts) == terms


def test_matches_folder_names_in_any_unicode_form():
    terms = parse_in("Beyoncé", "Beyoncé - Halo.mp3")
    assert terms is not None
    assert terms.artist == "Beyoncé"


@pytest.mark.parametrize(
    "parts",
    [
        ("Rock", "Daft Punk - Around the World.mp3"),
        ("Justice - Cross", "Daft Punk - Around the World.mp3"),
        ("Daft Punk -", "Daft Punk - Da Funk.mp3"),
        ("Daft Punk", "One More Time.mp3"),
        ("Daft Punk.mp3",),
    ],
)
def test_rejects_paths_that_do_not_name_the_artist(parts: tuple[str, ...]):
    assert parse_in(*parts) is None


def test_file_at_the_drive_root_has_no_folder_album():
    assert parse_library_path(Path("/Daft Punk - Da Funk.mp3")) is None


@pytest.mark.parametrize(
    ("folder", "album"),
    [
        ("Queen - Innuendo (1991) [FLAC]", "Innuendo"),
        ("Queen - Innuendo (Disc 1)", "Innuendo"),
        ("Queen - Innuendo (Deluxe Edition)", "Innuendo (Deluxe Edition)"),
        ("Queen - Discography", ""),
        ("Queen - Singles", ""),
        ("Queen - Discography (1973-1995)", ""),
        ("Queen - Room (101)", "Room (101)"),
        ("Queen - Innuendo (320 kbps)", "Innuendo"),
    ],
)
def test_cleans_the_folder_album(folder: str, album: str):
    assert get_album_in(folder, "Queen - Bicycle.mp3") == album


def test_folder_terms_come_from_the_library_path_first():
    source = ROOT / "Queen" / "Queen - Jazz" / "Queen - Bicycle.mp3"
    assert infer_library_folder_terms(source, ROOT) == FolderSearchTerms("Queen", "Jazz")


def test_folder_terms_fall_back_to_folder_context():
    source = ROOT / "Rock" / "Best Songs" / "Track.mp3"
    assert infer_library_folder_terms(source, ROOT) == FolderSearchTerms("Rock", "Best Songs")


def test_collapses_parent_segments_before_reading_folders():
    terms = parse_in("Queen", "Queen - Jazz", "CD1", "..", "Queen - a.mp3")
    assert terms == LibraryPathTerms("a", "Queen", "Jazz")
