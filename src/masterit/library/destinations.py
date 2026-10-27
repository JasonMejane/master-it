from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from masterit.library.relocation_problems import RelocationProblem
from masterit.library.rename_rules import RenameRule


@dataclass(frozen=True)
class Destination:
    folder: Path
    file_name: str
    problem: RelocationProblem | None = None

    @property
    def path(self) -> Path:
        return self.folder / self.file_name


type DestinationMaker = Callable[[Path], Destination]


def make_rename_destination(rule: RenameRule) -> DestinationMaker:
    def make_destination(source: Path) -> Destination:
        return Destination(source.parent, rule.make_name(source.stem) + source.suffix)

    return make_destination


def make_move_destination(folder: Path) -> DestinationMaker:
    def make_destination(source: Path) -> Destination:
        return Destination(folder, source.name)

    return make_destination
