import re
from pathlib import Path

from masterit.tagging.ascii_words import WORD_END, WORD_START
from masterit.tagging.paths.absolute_path import get_relative_folders, make_absolute
from masterit.tagging.paths.terms import FolderSearchTerms
from masterit.tagging.paths.track_name import clean_filename_part, split_label

STRUCTURAL_DIRECTORY_PATTERNS = [
    re.compile(
        r"^(?:(?:artist|album|artiste)\s+)?(?:unknown|inconnu|unknown artist|unknown album"
        r"|artiste inconnu|album inconnu|various artists|va|miscellaneous|misc)$"
    ),
    re.compile(r"^(?:cover|covers|artwork|booklet|cd|disc|disk)(?:[\s._-]*[0-9]+)?$"),
    re.compile(r"^(?:music|musique|audio|media|library|bibliothèque|itunes music)$"),
    re.compile(r"^[0-9]{4}(?:\s*[-._]\s*[0-9]{4})?$"),
    re.compile(r"^(?:part|partie|volume|vol\.?)[\s._-]*[0-9]+$"),
]
ALBUM_MARKER = re.compile(
    rf"{WORD_START}(?:ost|soundtrack|compilation|best of|greatest hits){WORD_END}", re.I
)
YEAR_PREFIX = re.compile(r"^\s*[0-9]{4}\s*[-._]\s*")


def is_structural_directory(name: str) -> bool:
    normalized = name.strip().lower()
    return not normalized or any(
        pattern.search(normalized) for pattern in STRUCTURAL_DIRECTORY_PATTERNS
    )


def clean_album_directory(name: str) -> str:
    return re.sub(r"\s+", " ", YEAR_PREFIX.sub("", name, count=1)).strip()


def get_meaningful_directories(filename: Path, source_root: Path) -> list[str]:
    folders = get_relative_folders(make_absolute(filename).parent, make_absolute(source_root))
    return [folder for folder in folders if not is_structural_directory(folder)]


def split_artist_and_album(album_label: str) -> FolderSearchTerms | None:
    if ALBUM_MARKER.search(album_label):
        return None
    artist, album = split_label(album_label)
    terms = FolderSearchTerms(clean_filename_part(artist), clean_album_directory(album))
    return terms if terms.artist and terms.album else None


def infer_from_combined_folder(directory: str) -> FolderSearchTerms:
    album_label = clean_album_directory(directory)
    return split_artist_and_album(album_label) or FolderSearchTerms(album=album_label)


def infer_from_nested_folders(directories: list[str]) -> FolderSearchTerms:
    artist_directory, album_directory = directories[-2:]
    return FolderSearchTerms(
        clean_filename_part(artist_directory), clean_album_directory(album_directory)
    )


def infer_folder_search_terms(filename: Path, source_root: Path) -> FolderSearchTerms:
    directories = get_meaningful_directories(filename, source_root)
    if not directories:
        return FolderSearchTerms()
    if len(directories) == 1:
        return infer_from_combined_folder(directories[0])
    return infer_from_nested_folders(directories)
