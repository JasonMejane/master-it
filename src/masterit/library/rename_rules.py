import re
from dataclasses import dataclass
from typing import Protocol

# Removed text is first replaced by a marker so the tidy-up only touches its surroundings.
REMOVED = "\x00"
SEPARATOR_CHARS = r"\-\u2013\u2014\uff5c|_,"
SEPARATORS = r"[\s" + SEPARATOR_CHARS + "]*"
REPEATED_REMOVALS = re.compile(REMOVED + r"(?:\s*" + REMOVED + ")+")
EMPTIED_BRACKETS = re.compile(r"[\(\[]\s*" + REMOVED + r"\s*[\)\]]")
BRACKET_SIDE_REMOVAL = re.compile(
    r"(?<=[\(\[])\s*" + REMOVED + r"\s*|\s*" + REMOVED + r"\s*(?=[\)\]])"
)
# Separators go with the removal only when whitespace sets them apart from the kept text.
EDGE_REMOVAL = re.compile(
    "^" + REMOVED + "(?:" + SEPARATORS + r"\s)?|(?:\s" + SEPARATORS + ")?" + REMOVED + "$"
)
SEPARATED_REMOVAL = re.compile(
    r"\s*[" + SEPARATOR_CHARS + r"]+\s*" + REMOVED + r"(?=\s*[" + SEPARATOR_CHARS + "])"
)
INNER_REMOVAL = re.compile(r"(\s*)" + REMOVED + r"(\s*)")


class RenameRule(Protocol):
    def make_name(self, stem: str) -> str: ...


def tidy_removal(marked: str) -> str:
    merged = merge_removals(EMPTIED_BRACKETS.sub(REMOVED, merge_removals(marked)))
    without_edges = EDGE_REMOVAL.sub("", BRACKET_SIDE_REMOVAL.sub("", merged))
    return INNER_REMOVAL.sub(join_around_removal, SEPARATED_REMOVAL.sub("", without_edges))


def merge_removals(marked: str) -> str:
    return REPEATED_REMOVALS.sub(REMOVED, marked)


def join_around_removal(match: re.Match[str]) -> str:
    return " " if match.group(1) or match.group(2) else ""


@dataclass(frozen=True)
class RemoveText:
    text: str

    def make_name(self, stem: str) -> str:
        if not self.text:
            return stem
        marked, count = re.subn(re.escape(self.text), REMOVED, stem, flags=re.IGNORECASE)
        return tidy_removal(marked) if count else stem


@dataclass(frozen=True)
class AddPrefix:
    text: str

    def make_name(self, stem: str) -> str:
        return self.text + stem


@dataclass(frozen=True)
class AddSuffix:
    text: str

    def make_name(self, stem: str) -> str:
        return stem + self.text


@dataclass(frozen=True)
class SetName:
    name: str

    def make_name(self, stem: str) -> str:
        return self.name.strip()
