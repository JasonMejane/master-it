from pathlib import Path

import pytest

from masterit.gui import move_job
from masterit.gui.move_job import MoveJob
from masterit.library.destinations import make_move_destination
from masterit.library.relocation import RelocationOutcome, RelocationPlan, make_relocation_plan


def run_job(job: MoveJob) -> list[object]:
    emitted: list[object] = []

    def record_progress(done: int, total: int) -> None:
        emitted.append((done, total))

    job.signals.progress.connect(record_progress)
    job.signals.crashed.connect(emitted.append)
    job.signals.finished.connect(emitted.append)
    job.run()
    return emitted


def make_plan(tmp_path: Path) -> RelocationPlan:
    (tmp_path / "list").mkdir()
    sources = [tmp_path / "list/A.mp3", tmp_path / "list/B.mp3"]
    for source in sources:
        source.touch()
    return make_relocation_plan(sources, make_move_destination(tmp_path / "dest"))


def make_job(tmp_path: Path, boundary: Path | None) -> MoveJob:
    return MoveJob(make_plan(tmp_path), boundary, lambda folder: False)


def test_job_moves_files_with_progress_then_cleans_up(tmp_path: Path):
    emitted = run_job(make_job(tmp_path, tmp_path))
    dest = tmp_path / "dest"
    assert emitted == [
        (1, 2),
        (2, 2),
        [
            RelocationOutcome(tmp_path / "list/A.mp3", dest / "A.mp3"),
            RelocationOutcome(tmp_path / "list/B.mp3", dest / "B.mp3"),
        ],
    ]
    assert not (tmp_path / "list").exists()


def test_job_without_boundary_keeps_emptied_folders(tmp_path: Path):
    run_job(make_job(tmp_path, None))
    assert (tmp_path / "list").is_dir()


def test_job_reports_crash_then_finishes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def crash(source: Path, target: Path) -> RelocationOutcome:
        raise RuntimeError("boom")

    monkeypatch.setattr(move_job, "relocate_file", crash)
    assert run_job(make_job(tmp_path, tmp_path)) == ["boom", []]


def test_job_keeps_protected_folders(tmp_path: Path):
    run_job(MoveJob(make_plan(tmp_path), tmp_path, lambda folder: folder.name == "list"))
    assert (tmp_path / "list").is_dir()
