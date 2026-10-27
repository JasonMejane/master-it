from pathlib import Path

import pytest

from masterit.gui import tag_job
from masterit.gui.tag_job import TagJob
from masterit.tags.fields import TagField, Tags
from masterit.tags.tag_edits import TagOutcome
from masterit.tags.tag_store import TagStore

from ..tags.fakes import FakeTagStore

PATHS = [Path("/a.mp3"), Path("/b.mp3")]


def run_job(job: TagJob) -> list[object]:
    emitted: list[object] = []

    def record_progress(done: int, total: int) -> None:
        emitted.append((done, total))

    job.signals.progress.connect(record_progress)
    job.signals.crashed.connect(emitted.append)
    job.signals.finished.connect(emitted.append)
    job.run()
    return emitted


def test_job_writes_edits_with_progress():
    store = FakeTagStore(failing={PATHS[1]})
    emitted = run_job(TagJob(PATHS, {TagField.GENRE: "Rock"}, store))
    assert emitted == [
        (1, 2),
        (2, 2),
        [TagOutcome(PATHS[0]), TagOutcome(PATHS[1], "read-only")],
    ]
    assert store.tags == {PATHS[0]: {TagField.GENRE: "Rock"}}


def test_job_reports_crash_then_finishes(monkeypatch: pytest.MonkeyPatch):
    def crash(path: Path, edits: Tags, store: TagStore) -> TagOutcome:
        raise RuntimeError("boom")

    monkeypatch.setattr(tag_job, "write_tag_edits", crash)
    assert run_job(TagJob(PATHS, {}, FakeTagStore())) == ["boom", []]
