from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from masterit.library.destinations import Destination
from masterit.library.library_layout import TagReader, make_layout_destination
from masterit.library.relocation import RelocationOutcome, RelocationPlan, make_relocation_plan


@dataclass(frozen=True)
class RepackPlan:
    moves: RelocationPlan
    # Already where the layout wants them: tagged without moving.
    in_place: tuple[Path, ...]

    def get_files_to_tag(self, outcomes: Iterable[RelocationOutcome]) -> list[Path]:
        moved = [outcome.target for outcome in outcomes if outcome.succeeded]
        return [*self.in_place, *moved]


def make_repack_plan(paths: list[Path], root: Path, read_tags: TagReader) -> RepackPlan:
    make_destination = make_layout_destination(root, read_tags)
    in_place = tuple(path for path in paths if is_in_place(path, make_destination(path)))
    return RepackPlan(make_relocation_plan(paths, make_destination), in_place)


def is_in_place(path: Path, destination: Destination) -> bool:
    return destination.problem is None and destination.path == path
