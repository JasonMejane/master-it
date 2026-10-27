import re
from dataclasses import fields, replace

from masterit.tagging.ascii_words import WORD_END, WORD_START
from masterit.tagging.metadata.types import TrackExtras, TrackInfo, TrackMetadata, TrackSearch

type ExtraGroup = tuple[str, ...]

YEAR_PATTERN = re.compile(rf"{WORD_START}[0-9]{{4}}{WORD_END}")
TRACK_FIELDS = tuple(field.name for field in fields(TrackInfo))
# A count only makes sense with the position it came from, so they move together.
EXTRA_GROUPS: tuple[ExtraGroup, ...] = (
    ("genre",),
    ("album_artist",),
    ("track_number", "track_count"),
    ("disc_number", "disc_count"),
)


def pick_filled(value: str, fallback: str) -> str:
    return value if value.strip() else fallback


def fill_missing_fields(info: TrackInfo, candidate: TrackInfo) -> TrackInfo:
    return TrackInfo(
        *(pick_filled(getattr(info, name), getattr(candidate, name)) for name in TRACK_FIELDS)
    )


def has_any_field(extras: TrackExtras, group: ExtraGroup) -> bool:
    return any(getattr(extras, name) is not None for name in group)


def has_lead_field(extras: TrackExtras, group: ExtraGroup) -> bool:
    return getattr(extras, group[0]) is not None


def pick_group(extras: TrackExtras, group: ExtraGroup) -> dict[str, object]:
    return {name: getattr(extras, name) for name in group}


def combine_groups(groups: list[dict[str, object]]) -> TrackExtras:
    return replace(
        TrackExtras(), **{name: value for group in groups for name, value in group.items()}
    )


def pick_filled_group(
    extras: TrackExtras, candidate: TrackExtras, group: ExtraGroup
) -> dict[str, object]:
    keeps_current = has_any_field(extras, group) or not has_lead_field(candidate, group)
    return pick_group(extras if keeps_current else candidate, group)


def fill_missing_extras(extras: TrackExtras, candidate: TrackExtras) -> TrackExtras:
    return combine_groups([pick_filled_group(extras, candidate, group) for group in EXTRA_GROUPS])


# A field the service did not find is no change.
def is_changed_group(existing: TrackExtras, found: TrackExtras, group: ExtraGroup) -> bool:
    return any(
        getattr(found, name) is not None and getattr(found, name) != getattr(existing, name)
        for name in group
    )


def get_changed_groups(existing: TrackExtras, found: TrackExtras) -> list[ExtraGroup]:
    return [group for group in EXTRA_GROUPS if is_changed_group(existing, found, group)]


def get_changed_extras(existing: TrackExtras, found: TrackExtras) -> TrackExtras:
    changed_groups = get_changed_groups(existing, found)
    return combine_groups([pick_group(found, group) for group in changed_groups])


# A count from the old position would not fit the new one.
def get_stale_extras(existing: TrackExtras, found: TrackExtras) -> list[str]:
    return [
        name
        for group in get_changed_groups(existing, found)
        for name in group
        if getattr(found, name) is None and getattr(existing, name) is not None
    ]


def has_all_details(metadata: TrackMetadata) -> bool:
    has_all_extras = all(has_lead_field(metadata.extras, group) for group in EXTRA_GROUPS)
    return has_all_extras and bool(metadata.info.year.strip())


def make_optional_text(value: str | None) -> str | None:
    return (value or "").strip() or None


def make_optional_count(value: int | None) -> int | None:
    return value if value and value > 0 else None


def has_changed_fields(existing: TrackInfo, found: TrackInfo) -> bool:
    return any(
        getattr(found, name).strip() and getattr(found, name) != getattr(existing, name)
        for name in TRACK_FIELDS
    )


def get_first_filled(*values: str | None) -> str:
    return next((value for value in values if value), "")


def merge_metadata(current: TrackMetadata, candidate: TrackMetadata) -> TrackMetadata:
    return TrackMetadata(
        fill_missing_fields(current.info, candidate.info),
        fill_missing_extras(current.extras, candidate.extras),
        current.cover_data if current.cover_data is not None else candidate.cover_data,
    )


def has_required_extras(extras: TrackExtras) -> bool:
    return bool(extras.genre) and bool(extras.track_number)


def has_all_fields(info: TrackInfo) -> bool:
    return all(getattr(info, name).strip() for name in TRACK_FIELDS)


def is_complete(metadata: TrackMetadata, has_existing_cover: bool) -> bool:
    has_cover = has_existing_cover or metadata.cover_data is not None
    return has_cover and has_required_extras(metadata.extras) and has_all_fields(metadata.info)


def extract_year(text: str | None) -> str:
    match = YEAR_PATTERN.search(text or "")
    return match.group() if match else ""


def build_provider_search(search: TrackSearch, info: TrackInfo) -> TrackSearch:
    return TrackSearch(
        pick_filled(info.title, search.title),
        pick_filled(info.artist, search.artist),
        pick_filled(search.album, info.album),
    )
