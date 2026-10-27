from pathlib import Path

from masterit.library.relocation import RelocationOutcome, RelocationProblem
from masterit.repack.pipeline import make_repack_plan
from masterit.tags.fields import TagField, Tags

ROOT = Path("/library")
DOWNLOADED = Path("/downloads/Queen - Mustapha.mp3")
IN_PLACE = ROOT / "ABBA" / "ABBA - SOS.opus"
UNTAGGED = Path("/downloads/unknown.mp3")
TAGS = {
    DOWNLOADED: {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"},
    IN_PLACE: {TagField.ARTIST: "ABBA", TagField.TITLE: "SOS"},
}


def read_tags(path: Path) -> Tags:
    return TAGS.get(path, {})


def test_plan_moves_files_into_layout_and_keeps_files_in_place():
    plan = make_repack_plan([DOWNLOADED, IN_PLACE, UNTAGGED], ROOT, read_tags)
    moves = [(entry.source, entry.target, entry.problem) for entry in plan.moves.entries]
    assert moves == [
        (DOWNLOADED, ROOT / "Queen" / "Queen - Mustapha.mp3", None),
        (UNTAGGED, UNTAGGED, RelocationProblem.MISSING_TAGS),
    ]
    assert plan.in_place == (IN_PLACE,)


def test_files_to_tag_are_files_in_place_and_moved_targets():
    plan = make_repack_plan([DOWNLOADED, IN_PLACE], ROOT, read_tags)
    target = ROOT / "Queen" / "Queen - Mustapha.mp3"
    outcomes = [
        RelocationOutcome(DOWNLOADED, target),
        RelocationOutcome(Path("/downloads/b.mp3"), ROOT / "b.mp3", "disk full"),
    ]
    assert plan.get_files_to_tag(outcomes) == [IN_PLACE, target]
