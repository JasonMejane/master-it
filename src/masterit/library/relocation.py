import errno
import re
import shutil
from collections import Counter
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from masterit.library.destinations import Destination, DestinationMaker
from masterit.library.relocation_problems import RelocationProblem

# Also rejects names Windows cannot read, as the library may live on an NTFS drive.
INVALID_NAME_PATTERN = re.compile(r'[/\\:*?"<>|\x00-\x1f]|^\.')

type FolderCheck = Callable[[Path], bool]


@dataclass(frozen=True)
class Relocation:
    source: Path
    target: Path
    problem: RelocationProblem | None = None

    @property
    def is_valid(self) -> bool:
        return self.problem is None


@dataclass(frozen=True)
class RelocationPlan:
    entries: tuple[Relocation, ...]

    @property
    def valid_entries(self) -> list[Relocation]:
        return [entry for entry in self.entries if entry.is_valid]


@dataclass(frozen=True)
class RelocationOutcome:
    source: Path
    target: Path
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def make_relocation_plan(
    paths: Iterable[Path], make_destination: DestinationMaker
) -> RelocationPlan:
    moves = [(path, make_destination(path)) for path in paths]
    changes = [(path, destination) for path, destination in moves if is_change(path, destination)]
    target_counts = Counter(destination.path for _, destination in changes)
    return RelocationPlan(
        tuple(make_relocation(path, destination, target_counts) for path, destination in changes)
    )


def is_change(source: Path, destination: Destination) -> bool:
    return destination.path != source or destination.problem is not None


def make_relocation(
    source: Path, destination: Destination, target_counts: Counter[Path]
) -> Relocation:
    name = destination.file_name
    target = destination.path
    failures = (
        (destination.problem, destination.problem is not None),
        (RelocationProblem.EMPTY_NAME, not name.removesuffix(source.suffix).strip()),
        (RelocationProblem.INVALID_NAME, INVALID_NAME_PATTERN.search(name) is not None),
        (RelocationProblem.DUPLICATE_TARGET, target_counts[target] > 1),
        (RelocationProblem.TARGET_EXISTS, is_taken(source, target)),
    )
    problem = next((problem for problem, failed in failures if failed), None)
    return Relocation(source, target, problem)


def is_taken(source: Path, target: Path) -> bool:
    return target.exists() and not target.samefile(source)


def apply_relocation_plan(plan: RelocationPlan) -> list[RelocationOutcome]:
    return [relocate_file(entry.source, entry.target) for entry in plan.valid_entries]


def relocate_file(source: Path, target: Path) -> RelocationOutcome:
    try:
        if is_taken(source, target):
            return RelocationOutcome(source, target, RelocationProblem.TARGET_EXISTS)
        target.parent.mkdir(parents=True, exist_ok=True)
        move_file(source, target)
    except OSError as error:
        return RelocationOutcome(source, target, str(error))
    return RelocationOutcome(source, target)


def move_file(source: Path, target: Path) -> None:
    try:
        source.rename(target)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        copy_then_delete(source, target)


def copy_then_delete(source: Path, target: Path) -> None:
    copy_exclusively(source, target)
    try:
        source.unlink()
    except FileNotFoundError:
        raise  # Someone else removed the source: the copy is now the only one.
    except OSError:
        remove_copy(target)
        raise


def copy_exclusively(source: Path, target: Path) -> None:
    target_file = target.open("xb")
    try:
        with target_file, source.open("rb") as source_file:
            shutil.copyfileobj(source_file, target_file)
    except OSError:
        remove_copy(target)
        raise
    # Some drives (e.g. ntfs3) may refuse dates or permissions; the audio data is what matters.
    with suppress(OSError):
        shutil.copystat(source, target)


def remove_copy(target: Path) -> None:
    with suppress(OSError):
        target.unlink(missing_ok=True)


def remove_emptied_folders(
    outcomes: list[RelocationOutcome], boundary: Path, is_protected: FolderCheck
) -> None:
    root = boundary.resolve()
    for folder in {outcome.source.parent.resolve() for outcome in outcomes if outcome.succeeded}:
        remove_empty_parents(folder, root, is_protected)


def remove_empty_parents(folder: Path, boundary: Path, is_protected: FolderCheck) -> None:
    current = folder
    while is_removable(current, boundary, is_protected):
        if not try_remove_folder(current):
            return
        current = current.parent


def is_removable(folder: Path, boundary: Path, is_protected: FolderCheck) -> bool:
    return is_strictly_inside(folder, boundary) and not is_protected(folder) and is_empty(folder)


def is_strictly_inside(folder: Path, boundary: Path) -> bool:
    return folder != boundary and folder.is_relative_to(boundary)


def is_empty(folder: Path) -> bool:
    return folder.is_dir() and not any(folder.iterdir())


def try_remove_folder(folder: Path) -> bool:
    try:
        folder.rmdir()
    except OSError:
        return False
    return True


def replace_relocated_paths(paths: list[Path], outcomes: list[RelocationOutcome]) -> list[Path]:
    targets = {outcome.source: outcome.target for outcome in outcomes if outcome.succeeded}
    return [targets.get(path, path) for path in paths]
