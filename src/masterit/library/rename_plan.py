import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from masterit.library.rename_rules import RenameRule

# Also rejects names Windows cannot read, as the library may live on an NTFS drive.
INVALID_NAME_PATTERN = re.compile(r'[/\\:*?"<>|\x00-\x1f]|^\.')


class RenameProblem(StrEnum):
    EMPTY_NAME = "Name is empty"
    INVALID_NAME = 'Name starts with "." or contains / \\ : * ? " < > | or a control character'
    DUPLICATE_TARGET = "Several files would get this name"
    TARGET_EXISTS = "A file with this name already exists"


@dataclass(frozen=True)
class RenameEntry:
    source: Path
    target: Path
    problem: RenameProblem | None = None

    @property
    def is_valid(self) -> bool:
        return self.problem is None


@dataclass(frozen=True)
class RenamePlan:
    entries: tuple[RenameEntry, ...]

    @property
    def valid_entries(self) -> list[RenameEntry]:
        return [entry for entry in self.entries if entry.is_valid]


@dataclass(frozen=True)
class RenameOutcome:
    source: Path
    target: Path
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def make_rename_plan(paths: Iterable[Path], rule: RenameRule) -> RenamePlan:
    renames = [(path, rule.make_name(path.stem)) for path in paths]
    changes = [(path, name) for path, name in renames if name != path.stem]
    target_counts = Counter(get_target(path, name) for path, name in changes)
    return RenamePlan(tuple(make_entry(path, name, target_counts) for path, name in changes))


def get_target(source: Path, name: str) -> Path:
    return source.parent / f"{name}{source.suffix}"


def make_entry(source: Path, name: str, target_counts: Counter[Path]) -> RenameEntry:
    target = get_target(source, name)
    failures = (
        (RenameProblem.EMPTY_NAME, not name.strip()),
        (RenameProblem.INVALID_NAME, INVALID_NAME_PATTERN.search(name) is not None),
        (RenameProblem.DUPLICATE_TARGET, target_counts[target] > 1),
        (RenameProblem.TARGET_EXISTS, is_taken(source, target)),
    )
    return RenameEntry(
        source, target, next((problem for problem, failed in failures if failed), None)
    )


def is_taken(source: Path, target: Path) -> bool:
    return target.exists() and not target.samefile(source)


def apply_rename_plan(plan: RenamePlan) -> list[RenameOutcome]:
    return [rename_file(entry.source, entry.target) for entry in plan.valid_entries]


def rename_file(source: Path, target: Path) -> RenameOutcome:
    try:
        if is_taken(source, target):
            return RenameOutcome(source, target, RenameProblem.TARGET_EXISTS)
        source.rename(target)
    except OSError as error:
        return RenameOutcome(source, target, str(error))
    return RenameOutcome(source, target)


def replace_renamed_paths(paths: list[Path], outcomes: list[RenameOutcome]) -> list[Path]:
    targets = {outcome.source: outcome.target for outcome in outcomes if outcome.succeeded}
    return [targets.get(path, path) for path in paths]
