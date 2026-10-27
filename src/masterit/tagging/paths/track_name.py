import re
from pathlib import PurePath

from masterit.tagging.paths.terms import TrackSearchTerms

LABEL_SEPARATOR = re.compile(r"\s+-\s+|\s*[\u2013\u2014]\s*")
TRACK_NUMBER_PREFIX = re.compile(r"^\s*(?:[0-9]{1,2}[._-][0-9]{1,2}|[0-9]{1,3})(?:\s*[-._]\s*|\s+)")


# JavaScript's trim also drops the byte order mark that some tools write into names.
def clean_filename_part(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[._\ufeff]+", " ", value)).strip()


def split_label(label: str) -> tuple[str, str]:
    separator = LABEL_SEPARATOR.search(label)
    if separator is None:
        return ("", "")
    return (label[: separator.start()], label[separator.end() :])


def split_artist_and_title(name: str) -> TrackSearchTerms | None:
    artist, title = (clean_filename_part(part) for part in split_label(name))
    return TrackSearchTerms(title, artist) if artist and title else None


def parse_track_filename(filename: str) -> TrackSearchTerms:
    name = clean_filename_part(TRACK_NUMBER_PREFIX.sub("", PurePath(filename).stem, count=1))
    return split_artist_and_title(name) or TrackSearchTerms(name)
