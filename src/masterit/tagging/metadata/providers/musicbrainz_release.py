from dataclasses import dataclass

from masterit.tagging.metadata.track_metadata import extract_year, make_optional_count
from masterit.tagging.metadata.types import TrackExtras
from masterit.tagging.web.json_fields import read_int, read_object, read_objects, read_text
from masterit.tagging.web.json_response import JsonObject


@dataclass(frozen=True)
class TrackPosition:
    medium: JsonObject
    track: JsonObject


def find_track_position(media: list[JsonObject], recording_id: str) -> TrackPosition | None:
    positions = (
        TrackPosition(medium, track) for medium in media for track in read_objects(medium, "tracks")
    )
    return next(
        (
            position
            for position in positions
            if read_text(read_object(position.track, "recording"), "id") == recording_id
        ),
        None,
    )


def get_track_position_extras(release: JsonObject, recording_id: str) -> TrackExtras:
    media = read_objects(release, "media")
    position = find_track_position(media, recording_id)
    if position is None:
        return TrackExtras()
    return TrackExtras(
        track_number=make_optional_count(read_int(position.track, "position")),
        track_count=make_optional_count(read_int(position.medium, "track-count")),
        disc_number=make_optional_count(read_int(position.medium, "position")),
        disc_count=make_optional_count(len(media)),
    )


def get_recording_date(media: list[JsonObject], recording_id: str) -> str | None:
    position = find_track_position(media, recording_id)
    if position is None:
        return None
    return read_text(read_object(position.track, "recording"), "first-release-date")


# A compilation dates late through its album and a remaster through its
# recording, so the earliest of both is closest to the song's first release.
def get_first_release_year(release: JsonObject, recording_id: str) -> str:
    recording_date = get_recording_date(read_objects(release, "media"), recording_id)
    album_date = read_text(read_object(release, "release-group"), "first-release-date")
    years = sorted(year for year in map(extract_year, (recording_date, album_date)) if year)
    return years[0] if years else ""
