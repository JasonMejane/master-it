from pathlib import Path

import pytest

from masterit.cancellation import CancelToken
from masterit.gui.auto_tag_jobs import TagRunJob, create_auto_tag_job, create_repack_job
from masterit.library import move_work
from masterit.library.library_layout import AlbumTarget
from masterit.library.relocation import RelocationOutcome
from masterit.repack.pipeline import RepackPlan, make_repack_plan
from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEventHandler,
    TaggingFinished,
)
from masterit.tags.fields import TagField

JAZZ = AlbumTarget("Queen", "Jazz")
FINISHED = TaggingFinished(tagged=1, skipped=0, failed=0, unprocessed=0, stopped=False)


class FakeTagger:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[list[Path]] = []
        self.error = error

    def tag(self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken):
        self.calls.append(paths)
        if self.error is not None:
            raise self.error
        for path in paths:
            on_event(FileAutoTagged(path, AutoTagStatus.TAGGED))
        on_event(FINISHED)


def record(job: TagRunJob) -> list[object]:
    emitted: list[object] = []
    job.signals.event_received.connect(emitted.append)
    job.signals.crashed.connect(emitted.append)
    job.signals.finished.connect(lambda: emitted.append("finished"))
    return emitted


def test_auto_tag_job_relays_tagger_events():
    tagger = FakeTagger()
    job = create_auto_tag_job(tagger, [Path("/a.mp3")], CancelToken())
    emitted = record(job)
    job.run()
    assert tagger.calls == [[Path("/a.mp3")]]
    assert emitted == [FileAutoTagged(Path("/a.mp3"), AutoTagStatus.TAGGED), FINISHED, "finished"]


def test_auto_tag_job_reports_crash_then_finishes():
    job = create_auto_tag_job(FakeTagger(RuntimeError("boom")), [Path("/a.mp3")], CancelToken())
    emitted = record(job)
    job.run()
    assert emitted == ["boom", "finished"]


def make_repack_job(tmp_path: Path, tagger: FakeTagger, token: CancelToken) -> TagRunJob:
    source = tmp_path / "dl" / "song.mp3"
    source.parent.mkdir()
    source.touch()
    tags = {TagField.ARTIST: "Queen", TagField.TITLE: "Mustapha"}
    plan = make_repack_plan([source], tmp_path / "lib", JAZZ, lambda path: tags)
    return create_repack_job(plan, tmp_path / "dl", lambda folder: False, tagger, token)


def test_repack_job_moves_then_tags_moved_files(tmp_path: Path):
    tagger = FakeTagger()
    job = make_repack_job(tmp_path, tagger, CancelToken())
    moved: list[list[RelocationOutcome]] = []
    progress: list[tuple[int, int]] = []
    job.signals.moved.connect(moved.append)

    def record_progress(done: int, total: int) -> None:
        progress.append((done, total))

    job.signals.move_progress.connect(record_progress)
    emitted = record(job)
    job.run()
    target = tmp_path / "lib" / "Queen" / "Queen - Jazz" / "Queen - Mustapha.mp3"
    assert moved == [[RelocationOutcome(tmp_path / "dl" / "song.mp3", target)]]
    assert progress == [(1, 1)]
    assert tagger.calls == [[target]]
    assert emitted[-1] == "finished"
    assert not (tmp_path / "dl" / "song.mp3").exists()


def test_repack_job_cancelled_during_move_skips_tagging(tmp_path: Path):
    tagger = FakeTagger()
    token = CancelToken()
    token.cancel()
    job = make_repack_job(tmp_path, tagger, token)
    emitted = record(job)
    job.run()
    assert tagger.calls == []
    assert emitted == ["finished"]


def test_repack_job_reports_moves_done_before_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def crash(source: Path, target: Path) -> RelocationOutcome:
        raise RuntimeError("boom")

    monkeypatch.setattr(move_work, "relocate_file", crash)
    tagger = FakeTagger()
    job = make_repack_job(tmp_path, tagger, CancelToken())
    moved: list[object] = []
    job.signals.moved.connect(moved.append)
    emitted = record(job)
    job.run()
    assert moved == [[]]
    assert emitted == ["boom", "finished"]
    assert tagger.calls == []


def test_repack_job_without_files_to_tag_skips_the_tagger(tmp_path: Path):
    tagger = FakeTagger()
    plan = make_repack_plan([], tmp_path / "lib", JAZZ, lambda path: {})
    job = make_repack_job_from(plan, tmp_path, tagger)
    emitted = record(job)
    job.run()
    assert tagger.calls == []
    assert emitted == ["finished"]


def make_repack_job_from(plan: RepackPlan, tmp_path: Path, tagger: FakeTagger) -> TagRunJob:
    return create_repack_job(plan, tmp_path, lambda folder: False, tagger, CancelToken())
