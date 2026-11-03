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
# yt-dlp writes these lookalikes for characters that file names refuse.
FILE_NAME_LOOKALIKES = {
    "/": "\u29f8",
    "\\": "\u29f9",
    ":": "\uff1a",
    "|": "\uff5c",
    '"': "\uff02",
    "?": "\uff1f",
    "*": "\uff0a",
    "<": "\uff1c",
    ">": "\uff1e",
}
EQUIVALENT_CHARACTERS = {
    **FILE_NAME_LOOKALIKES,
    **{lookalike: plain for plain, lookalike in FILE_NAME_LOOKALIKES.items()},
}
SPACE_RUN = re.compile(r"\s+")


class RenameRule(Protocol):
    def make_name(self, stem: str) -> str: ...


def tidy_removal(marked: str) -> str:
    merged = merge_removals(EMPTIED_BRACKETS.sub(REMOVED, merge_removals(marked)))
    without_edges = EDGE_REMOVAL.sub("", BRACKET_SIDE_REMOVAL.sub("", merged))
    return INNER_REMOVAL.sub(join_around_removal, SEPARATED_REMOVAL.sub("", without_edges))


def make_loose_pattern(text: str) -> str:
    words = SPACE_RUN.split(text)
    return r"\s+".join("".join(map(make_character_pattern, word)) for word in words)


def make_character_pattern(character: str) -> str:
    equivalent = EQUIVALENT_CHARACTERS.get(character)
    if equivalent is None:
        return re.escape(character)
    return f"[{re.escape(character)}{re.escape(equivalent)}]"


def merge_removals(marked: str) -> str:
    return REPEATED_REMOVALS.sub(REMOVED, marked)


def join_around_removal(match: re.Match[str]) -> str:
    return " " if match.group(1) or match.group(2) else ""


@dataclass(frozen=True)
class RemoveText:
    text: str

    def make_name(self, stem: str) -> str:
        text = self.text.strip()
        if not text:
            return stem
        pattern = make_loose_pattern(text)
        marked, count = re.subn(pattern, REMOVED, stem, flags=re.IGNORECASE)
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
