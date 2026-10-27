import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from masterit.tagging.paths.absolute_path import make_absolute
from masterit.tagging.paths.folder_context import (
    clean_album_directory,
    infer_folder_search_terms,
    is_structural_directory,
)
from masterit.tagging.paths.terms import FolderSearchTerms, LibraryPathTerms, TrackSearchTerms
from masterit.tagging.paths.track_name import (
    clean_filename_part,
    parse_track_filename,
    split_label,
)

type FolderAlbumReader = Callable[[str, str], str | None]

# Rip details such as "(1991) [FLAC]" or "(Disc 1)" are not part of the album.
RIP_NOTES = re.compile(
    r"(?:\s*(?:\[[^\]]*\]|\((?:[0-9]{4}(?:\s*-\s*[0-9]{4})?|flac|mp3|[0-9]{3}\s*kbps|v[02]"
    r"|(?:cd|disc)\s*[0-9]+)\)))+$",
    re.I,
)
LOOSE_TRACK_FOLDER = re.compile(
    r"^(?:discography|discographie|singles|mp3|flac|misc|divers)$", re.I
)
# Only before a dash, so "99 Luftballons" keeps its number.
TITLE_TRACK_NUMBER = re.compile(r"^[0-9]{1,3}\s*-\s+")


def fold_name(name: str) -> str:
    return unicodedata.normalize("NFC", clean_filename_part(name)).lower()


def is_same_folder_name(folder: str, artist: str) -> bool:
    return fold_name(folder) == fold_name(artist)


def read_artist_folder(folder: str, artist: str) -> str | None:
    return "" if is_same_folder_name(folder, artist) else None


def clean_folder_album(album: str) -> str:
    cleaned = RIP_NOTES.sub("", clean_album_directory(album), count=1).strip()
    return "" if LOOSE_TRACK_FOLDER.search(cleaned) else cleaned


def is_named_folder(folder: str) -> bool:
    return not is_structural_directory(folder) and clean_folder_album(folder) != ""


def read_artist_album_folder(folder: str, artist: str) -> str | None:
    folder_artist, album = split_label(folder)
    is_album_folder = is_same_folder_name(folder_artist, artist) and album.strip()
    return clean_folder_album(album) if is_album_folder else None


FOLDER_ALBUM_READERS: list[FolderAlbumReader] = [read_artist_folder, read_artist_album_folder]


# Disc, artwork and loose-track ("Singles") folders sit between the album folder and its files.
def get_named_parent(filename: Path) -> str:
    parent = make_absolute(filename).parent
    folders = parent.relative_to(parent.anchor).parts
    return next((folder for folder in reversed(folders) if is_named_folder(folder)), "")


def read_folder_album(folder: str, artist: str) -> str | None:
    albums = (read(folder, artist) for read in FOLDER_ALBUM_READERS)
    return next((album for album in albums if album is not None), None)


def drop_album_prefix(title: str, album: str) -> str:
    prefix, rest = split_label(title)
    return rest if rest and is_same_folder_name(prefix, album) else title


# "Artist - Album - 01 - Title" names the album and track number again.
def clean_path_title(title: str, album: str) -> str:
    without_album = drop_album_prefix(title, album)
    return clean_filename_part(TITLE_TRACK_NUMBER.sub("", without_album, count=1))


def read_path_terms(filename: Path, terms: TrackSearchTerms) -> LibraryPathTerms | None:
    if not terms.artist:
        return None
    album = read_folder_album(get_named_parent(filename), terms.artist)
    if album is None:
        return None
    return LibraryPathTerms(clean_path_title(terms.title, album), terms.artist, album)


# Folders above the scanned one count too: the file's artist vouches for them.
def parse_library_path(filename: Path) -> LibraryPathTerms | None:
    return read_path_terms(filename, parse_track_filename(filename.name))


def infer_library_folder_terms(filename: Path, source_root: Path) -> FolderSearchTerms:
    terms = parse_library_path(filename)
    if terms is None:
        return infer_folder_search_terms(filename, source_root)
    return FolderSearchTerms(terms.artist, terms.album)
