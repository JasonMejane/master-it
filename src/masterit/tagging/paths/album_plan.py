import re
from collections.abc import Callable
from pathlib import Path

from masterit.tagging.ascii_words import WORD_END
from masterit.tagging.paths.absolute_path import make_absolute
from masterit.tagging.paths.library_path import clean_folder_album, is_same_folder_name
from masterit.tagging.paths.terms import AlbumFolder, AlbumTrack, AlbumUnit, TrackPlan
from masterit.tagging.paths.track_name import split_label

type AlbumFileLister = Callable[[Path], list[Path]]
type SelectedAlbums = dict[Path, tuple[AlbumFolder, list[Path]]]

# "CD1", "Disc 2", "CD1 - Bonus".
DISC_FOLDER = re.compile(rf"^(?:cd|disc|disk)[\s._-]*([0-9]+){WORD_END}", re.I)
# "Album - CD2", "Album <en dash> CD2", "Album (Disc 2)".
DISC_SUFFIX = re.compile(r"\s*(?:[-\u2013]\s*|\()(?:cd|disc|disk)[\s._-]*([0-9]+)\)?$", re.I)
BRACKET_NOTES = re.compile(r"(?:\s*\[[^\]]*\])+$")


def read_disc(name: str, pattern: re.Pattern[str]) -> int | None:
    match = pattern.search(name)
    disc = int(match.group(1)) if match else 0
    return disc if disc > 0 else None


def read_disc_folder(file: Path) -> int | None:
    return read_disc(file.parent.name, DISC_FOLDER)


def get_album_folder_path(file: Path) -> Path:
    folder = file.parent
    return folder.parent if DISC_FOLDER.search(folder.name) else folder


def read_album_name(folder: Path) -> str:
    return BRACKET_NOTES.sub("", split_label(folder.name)[1], count=1)


def read_album_label(folder: Path) -> tuple[str, str]:
    artist = split_label(folder.name)[0]
    album = DISC_SUFFIX.sub("", read_album_name(folder), count=1)
    is_disc_name = DISC_FOLDER.search(album) is not None
    return (artist.strip(), "" if is_disc_name else clean_folder_album(album))


def is_below_artist(folder: Path, artist: str) -> bool:
    return artist != "" and is_same_folder_name(folder.parent.name, artist)


# A disc folder inside the album wins over a disc note on the album folder.
def read_track_disc(file: Path, folder: Path) -> int | None:
    return read_disc_folder(file) or read_disc(read_album_name(folder), DISC_SUFFIX)


def find_album_folder(file: Path) -> AlbumFolder | None:
    resolved = make_absolute(file)
    folder = get_album_folder_path(resolved)
    artist, album = read_album_label(folder)
    if not (album and is_below_artist(folder, artist)):
        return None
    return AlbumFolder(folder, artist, album, read_track_disc(resolved, folder))


# The album a folder belongs to: itself, or the album above its disc folder.
def find_folder_album(folder: Path) -> Path | None:
    album = find_album_folder(folder / "track")
    return album.folder if album else None


# A file may bring in its whole album, so it is searched from there.
def get_file_root(file: Path) -> Path:
    folder = make_absolute(file).parent
    return find_folder_album(folder) or folder


def is_in_album(file: Path, folder: Path) -> bool:
    album = find_album_folder(file)
    return album is not None and album.folder == folder


# Selected files stay in, even when the listing misses them.
def merge_tracks(listed: list[Path], selected: list[Path]) -> list[AlbumTrack]:
    files = dict.fromkeys(make_absolute(file) for file in [*listed, *selected])
    return [AlbumTrack(file, read_found_disc(file)) for file in files]


def read_found_disc(file: Path) -> int | None:
    album = find_album_folder(file)
    return album.disc if album else None


def make_album_unit(
    album: AlbumFolder, selected: list[Path], list_album_files: AlbumFileLister
) -> AlbumUnit:
    listed = [file for file in list_album_files(album.folder) if is_in_album(file, album.folder)]
    return AlbumUnit(album.folder, album.artist, album.album, merge_tracks(listed, selected))


def add_album_file(file: Path, albums: SelectedAlbums) -> bool:
    album = find_album_folder(file)
    if album is None:
        return False
    albums.setdefault(album.folder, (album, []))[1].append(file)
    return True


# Any file of an album folder brings in the whole album, so its tags stay alike.
def plan_tracks(files: list[Path], list_album_files: AlbumFileLister) -> TrackPlan:
    albums: SelectedAlbums = {}
    singles = [file for file in files if not add_album_file(file, albums)]
    units = [
        make_album_unit(album, selected, list_album_files) for album, selected in albums.values()
    ]
    return TrackPlan(units, singles)
