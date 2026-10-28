from masterit.tagging.metadata.track_metadata import (
    get_changed_extras,
    get_stale_extras,
    has_changed_fields,
)
from masterit.tagging.metadata.types import ExistingTags, TrackExtras, TrackMetadata
from masterit.tagging.track_tags import TagWrite

# MasterIt always overwrites: downloads already carry yt-dlp's tags, which filling would keep.


# Services search from no tags, but a stored cover is only replaced by a service's own.
def get_searched_tags(stored: ExistingTags) -> ExistingTags:
    return ExistingTags(has_cover=stored.has_cover)


def get_overwrite(stored: ExistingTags, found: TrackMetadata) -> TagWrite | None:
    extras = get_changed_extras(stored.extras, found.extras)
    has_new_info = has_changed_fields(stored.info, found.info)
    if not (has_new_info or extras != TrackExtras() or found.cover_data is not None):
        return None
    cleared = tuple(get_stale_extras(stored.extras, found.extras))
    return TagWrite(TrackMetadata(found.info, extras, found.cover_data), cleared)
