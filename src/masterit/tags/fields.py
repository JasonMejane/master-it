from enum import StrEnum


class TagField(StrEnum):
    # Values are mutagen easy-API keys, shared by ID3, MP4 and Vorbis comments.
    TITLE = "title"
    ARTIST = "artist"
    ALBUM = "album"
    ALBUM_ARTIST = "albumartist"
    YEAR = "date"
    GENRE = "genre"
    TRACK = "tracknumber"
    COMMENT = "comment"


type Tags = dict[TagField, str]
