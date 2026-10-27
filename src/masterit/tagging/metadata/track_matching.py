import re
import unicodedata
from dataclasses import dataclass

from masterit.tagging.ascii_words import WORD_END, WORD_START
from masterit.tagging.metadata.types import AlbumSearch, TrackSearch


@dataclass(frozen=True)
class FoundTrack:
    title: str | None = None
    artist: str | None = None


@dataclass(frozen=True)
class FoundAlbumName:
    album: str | None = None
    artist: str | None = None


@dataclass(frozen=True)
class FoundRelease:
    album: str | None = None
    album_artist: str | None = None
    track_artist: str | None = None


DASHES = "-\u2013\u2014"
# Notes that name another version (live, karaoke, remix) must still differ.
NOISE_BRACKET = re.compile(
    rf"[(\[][^)\]]*{WORD_START}(?:remaster(?:ed|s)?|feat|ft|explicit|mono|stereo){WORD_END}"
    r"[^)\]]*[)\]]"
)
NOISE_SUFFIX = re.compile(
    rf"\s[{DASHES}]\s[^{DASHES}]*{WORD_START}(?:remaster(?:ed|s)?|explicit|mono|stereo)"
    rf"{WORD_END}[^{DASHES}]*$"
)
# An album note may only hold a remaster: "(Deluxe Remastered Edition)" is another release.
ALBUM_NOTE = (
    r"(?:[0-9]{4}\s+)?(?:digital(?:ly)?\s+)?remaster(?:ed)?(?:\s+[0-9]{4})?"
    r"(?:\s+(?:version|edition))?"
)
ALBUM_NOTE_BRACKET = re.compile(rf"[(\[]\s*{ALBUM_NOTE}\s*[)\]]")
ALBUM_NOTE_SUFFIX = re.compile(rf"\s[{DASHES}]\s{ALBUM_NOTE}\s*$")
SPELLED_NOTE_BRACKET = re.compile(ALBUM_NOTE_BRACKET.pattern, re.I)
SPELLED_NOTE_SUFFIX = re.compile(ALBUM_NOTE_SUFFIX.pattern, re.I)
# Like JavaScript's "." and "$": no line terminator inside, no newline allowed after.
FEATURING_SUFFIX = re.compile(r"\s(?:feat\.?|ft\.|featuring)\s[^\n\r\u2028\u2029]*\Z")
# Letters and numbers of any script make words; marks are removed before.
WORD_SEPARATOR = re.compile(r"[\W_]+")
ARTIST_SEPARATOR = re.compile(r"\s+(?:feat\.?|ft\.?|featuring|&|and|x|with)\s+|\s*,\s*", re.I)
NOTE_START = re.compile(rf"\s*[(\[]|\s[{DASHES}]\s")
LEADING_ARTICLE = re.compile(r"^\s*the\s+(?=\S)", re.I)

# Shorter names are too often different words one letter apart.
MIN_TYPO_LENGTH = 9
MIN_TYPO_WORD_LENGTH = 5
NUMBER_WORD = re.compile(r"[0-9]|^[ivxlcdm]+$")
VARIOUS_ARTISTS = "variousartists"
# Folders and Discogs shorten it.
VARIOUS_CREDITS = frozenset({VARIOUS_ARTISTS, "various", "va"})


def fold_text(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(char for char in decomposed if not unicodedata.category(char).startswith("M"))


def split_words(text: str) -> list[str]:
    return [word for word in WORD_SEPARATOR.split(text) if word]


# Albums made only of symbols ("+", "÷") are compared as written.
def normalize_album(album: str | None) -> str:
    folded = fold_text(album)
    without_notes = ALBUM_NOTE_SUFFIX.sub("", ALBUM_NOTE_BRACKET.sub("", folded), count=1)
    return "".join(split_words(without_notes)) or folded.strip()


# The tag names the album, not the remaster a service lists.
def strip_remaster_note(album: str) -> str:
    without_bracket = SPELLED_NOTE_BRACKET.sub("", album)
    stripped = SPELLED_NOTE_SUFFIX.sub("", without_bracket, count=1).strip()
    return stripped or album


def is_same_album(found_album: str | None, searched_album: str) -> bool:
    return not searched_album or normalize_album(found_album) == normalize_album(searched_album)


def get_words(name: str | None) -> list[str]:
    without_brackets = NOISE_BRACKET.sub("", fold_text(name))
    without_suffix = NOISE_SUFFIX.sub("", without_brackets, count=1)
    return split_words(FEATURING_SUFFIX.sub("", without_suffix, count=1))


def get_common_prefix_length(first: str, second: str) -> int:
    length = 0
    while length < len(first) and first[length] == second[length]:
        length += 1
    return length


def is_one_edit_apart(shorter: str, longer: str) -> bool:
    length_gap = len(longer) - len(shorter)
    if length_gap > 1:
        return False
    prefix_length = get_common_prefix_length(shorter, longer)
    return shorter[prefix_length + 1 - length_gap :] == longer[prefix_length + 1 :]


# A changed number (track 2 vs 12, part I vs II) or plural names another work.
def is_meaningful_change(shorter: str, longer: str) -> bool:
    is_plural = f"{shorter}s" == longer
    return is_plural or any(NUMBER_WORD.search(word) for word in (shorter, longer))


def is_typo_word(first: str, second: str) -> bool:
    shorter, longer = sorted((first, second), key=len)
    return (
        len(longer) >= MIN_TYPO_WORD_LENGTH
        and is_one_edit_apart(shorter, longer)
        and not is_meaningful_change(shorter, longer)
    )


def can_hold_typo(found: list[str], searched: list[str]) -> bool:
    shortest_length = min(len("".join(found)), len("".join(searched)))
    return len(found) == len(searched) and shortest_length >= MIN_TYPO_LENGTH


def is_typo(found: list[str], searched: list[str]) -> bool:
    pairs = [
        (first, second) for first, second in zip(found, searched, strict=False) if first != second
    ]
    return can_hold_typo(found, searched) and len(pairs) == 1 and is_typo_word(*pairs[0])


def is_same_name(found: str | None, searched: str) -> bool:
    found_words = get_words(found)
    searched_words = get_words(searched)
    return "".join(found_words) == "".join(searched_words) or is_typo(found_words, searched_words)


def fold_words(text: str) -> str:
    return "".join(split_words(fold_text(text)))


# A name followed by a note: "Song (Live)", "Album (Deluxe Edition)", "Song - Live".
def has_note_after_name(name: str, start: str) -> bool:
    note = NOTE_START.search(name)
    head = fold_words(name[: note.start()]) if note else ""
    return bool(head) and head == fold_words(start)


def split_artists(credit: str | None) -> list[str]:
    return [artist for artist in ARTIST_SEPARATOR.split(credit or "") if get_words(artist)]


def remove_leading_article(name: str | None) -> str:
    return LEADING_ARTICLE.sub("", name or "", count=1)


# Services disagree on "The Black Eyed Peas" versus "Black Eyed Peas".
def is_same_artist_name(found: str | None, searched: str) -> bool:
    return is_same_name(found, searched) or is_same_name(
        remove_leading_article(found), remove_leading_article(searched)
    )


# Credits list featured artists in any order: "A feat. B", "B & A", "B, A".
def has_shared_artist(found: str | None, searched: str) -> bool:
    found_artists = split_artists(found)
    return any(
        is_same_artist_name(found_artist, searched_artist)
        for searched_artist in split_artists(searched)
        for found_artist in found_artists
    )


def is_same_artist(found: str | None, searched: str) -> bool:
    return is_same_artist_name(found, searched) or has_shared_artist(found, searched)


# The first search result can be a karaoke or cover version, whose extras would stick.
def is_same_track(found: FoundTrack, search: TrackSearch) -> bool:
    is_searched_artist = not search.artist or is_same_artist(found.artist, search.artist)
    return is_searched_artist and is_same_name(found.title, search.title)


def is_various_artists(artist: str) -> bool:
    return "".join(get_words(artist)) == VARIOUS_ARTISTS


def is_various_credit(artist: str | None) -> bool:
    return "".join(get_words(artist)) in VARIOUS_CREDITS


def is_same_album_artist(found: str | None, searched: str) -> bool:
    is_various = is_various_credit(found) and is_various_credit(searched)
    return is_various or is_same_artist(found, searched)


# The album must be by the searched artist, so another artist's namesake is not taken.
def is_searched_album(found: FoundAlbumName, search: AlbumSearch) -> bool:
    return is_same_album(found.album, search.album) and is_same_album_artist(
        found.artist, search.artist
    )


def is_album_artist_of(album_artist: str, track_artist: str) -> bool:
    return is_various_artists(album_artist) or is_same_artist(album_artist, track_artist)


# A cover band's record can list the original artist on its track.
def is_credited_release(release: FoundRelease) -> bool:
    if not (release.album_artist and release.track_artist):
        return True
    return is_album_artist_of(release.album_artist, release.track_artist)


# Numbers, year and cover from another release (compilation, single) would be wrong.
def is_same_release(release: FoundRelease, searched_album: str) -> bool:
    return is_same_album(release.album, searched_album) and is_credited_release(release)
