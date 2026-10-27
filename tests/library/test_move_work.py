from pathlib import Path

from masterit.library.destinations import make_move_destination
from masterit.library.move_work import MoveWork
from masterit.library.relocation import RelocationOutcome, make_relocation_plan


def make_work(tmp_path: Path, boundary: Path | None) -> MoveWork:
    (tmp_path / "list").mkdir()
    sources = [tmp_path / "list/A.mp3", tmp_path / "list/B.mp3"]
    for source in sources:
        source.touch()
    plan = make_relocation_plan(sources, make_move_destination(tmp_path / "dest"))
    return MoveWork(plan, boundary, lambda folder: False)


def test_moves_files_with_progress_then_cleans_up(tmp_path: Path):
    work = make_work(tmp_path, tmp_path)
    progress: list[tuple[int, int]] = []
    work.run(lambda done, total: progress.append((done, total)))
    dest = tmp_path / "dest"
    assert progress == [(1, 2), (2, 2)]
    assert work.outcomes == [
        RelocationOutcome(tmp_path / "list/A.mp3", dest / "A.mp3"),
        RelocationOutcome(tmp_path / "list/B.mp3", dest / "B.mp3"),
    ]
    assert not (tmp_path / "list").exists()


def test_without_boundary_keeps_emptied_folders(tmp_path: Path):
    make_work(tmp_path, None).run(lambda done, total: None)
    assert (tmp_path / "list").is_dir()
