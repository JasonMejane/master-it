import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_store import TagError, TagStore

FORMAT_RULES = {
    TagField.YEAR: (
        re.compile(r"\d{4}(-\d{2}(-\d{2})?)?"),
        "Year must look like 2024 or 2024-05-17.",
    ),
    TagField.TRACK: (
        re.compile(r"[1-9]\d{0,3}(/[1-9]\d{0,3})?"),
        "Track must look like 3 or 3/12.",
    ),
}


@dataclass(frozen=True)
class TagOutcome:
    path: Path
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def find_tag_problem(edits: Tags) -> str | None:
    for field, (pattern, problem) in FORMAT_RULES.items():
        value = edits.get(field, "")
        if value and not pattern.fullmatch(value):
            return problem
    return None


def merge_tag_values(selection: Sequence[Tags]) -> dict[TagField, str | None]:
    """Value shared by every file, or None when files differ."""
    return {field: get_shared_value(selection, field) for field in TagField}


def get_shared_value(selection: Sequence[Tags], field: TagField) -> str | None:
    values = {tags.get(field, "") for tags in selection}
    return values.pop() if len(values) == 1 else (None if values else "")


def write_tag_edits(path: Path, edits: Tags, store: TagStore) -> TagOutcome:
    try:
        store.write(path, edits)
    except TagError as error:
        return TagOutcome(path, str(error))
    return TagOutcome(path)
