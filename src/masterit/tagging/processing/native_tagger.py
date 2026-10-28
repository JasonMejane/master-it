from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from masterit.cancellation import CancelToken
from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEventHandler,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)
from masterit.tagging.metadata.types import AlbumData, AlbumFinder, AlbumSearch
from masterit.tagging.paths.album_plan import AlbumFileLister, plan_tracks
from masterit.tagging.paths.terms import AlbumTrack, AlbumUnit, TrackPlan
from masterit.tagging.processing.album_track import AlbumTrackTagger
from masterit.tagging.processing.single_track import SingleTrackTagger, TrackFinder
from masterit.tagging.processing.track_write import TagFiles, TrackOutcome
from masterit.tagging.stop_guard import RunAbortedError, StopGuard

type TrackTagging = Callable[[AlbumTrack], TrackOutcome]


class CachedTrackFinder(TrackFinder, Protocol):
    def clear_cache(self) -> None: ...


# A sibling disc folder ("Album - CD2") holds one disc, not the whole tracklist.
def get_folder_file_count(unit: AlbumUnit) -> int | None:
    discs = {track.disc for track in unit.tracks}
    return None if len(discs) == 1 and None not in discs else len(unit.tracks)


def count_tracks(plan: TrackPlan) -> int:
    return sum(len(unit.tracks) for unit in plan.albums) + len(plan.singles)


def describe_error(error: Exception) -> str:
    return str(error) or type(error).__name__


class AlbumLookupError(Exception):
    pass


# A failed lookup is remembered too, so the album's other tracks fail without asking again.
class AlbumSupplier:
    def __init__(self, albums: AlbumFinder, unit: AlbumUnit) -> None:
        self._albums = albums
        self._unit = unit
        self._result: AlbumData | str | None = None

    def get(self) -> AlbumData:
        if self._result is None:
            self._result = self._look_up()
        if isinstance(self._result, str):
            raise AlbumLookupError(self._result)
        return self._result

    def _look_up(self) -> AlbumData | str:
        search = AlbumSearch(self._unit.artist, self._unit.album)
        try:
            return self._albums.resolve(search, get_folder_file_count(self._unit))
        except RunAbortedError:
            raise
        except Exception as error:
            return describe_error(error)


# Like SoundTag, any error fails only its file, with the error as the reason.
def tag_safely(tag_track: TrackTagging, track: AlbumTrack) -> TrackOutcome:
    try:
        return tag_track(track)
    except RunAbortedError:
        raise
    except Exception as error:
        return TrackOutcome(AutoTagStatus.FAILED, describe_error(error))


class BatchRun:
    def __init__(self, on_event: TaggerEventHandler, cancel_token: CancelToken, total: int) -> None:
        self._on_event = on_event
        self._cancel_token = cancel_token
        self._total = total
        self._counts = dict.fromkeys(AutoTagStatus, 0)

    def process(self, tracks: list[AlbumTrack], tag_track: TrackTagging) -> bool:
        for track in tracks:
            outcome = self._try_tag(track, tag_track)
            if outcome is None:
                return False
            self._record(track.path, outcome)
        return True

    # None once stopped: before the file, or while it runs after a second stop.
    def _try_tag(self, track: AlbumTrack, tag_track: TrackTagging) -> TrackOutcome | None:
        if self._cancel_token.is_cancelled:
            return None
        try:
            return tag_safely(tag_track, track)
        except RunAbortedError:
            return None

    def make_finished(self) -> TaggingFinished:
        return TaggingFinished(
            tagged=self._counts[AutoTagStatus.TAGGED],
            skipped=self._counts[AutoTagStatus.SKIPPED],
            failed=self._counts[AutoTagStatus.FAILED],
            unprocessed=self._total - sum(self._counts.values()),
            stopped=self._cancel_token.is_cancelled,
        )

    def _record(self, path: Path, outcome: TrackOutcome) -> None:
        self._counts[outcome.status] += 1
        self._on_event(FileAutoTagged(path, outcome.status, outcome.reason))


class NativeTagger:
    def __init__(
        self,
        finder: CachedTrackFinder,
        albums: AlbumFinder,
        files: TagFiles,
        list_album_files: AlbumFileLister,
        stop_guard: StopGuard | None = None,
    ) -> None:
        self._stop_guard = stop_guard or StopGuard()
        self._finder = finder
        self._albums = albums
        self._list_album_files = list_album_files
        self._singles = SingleTrackTagger(finder, files)
        self._album_tracks = AlbumTrackTagger(files)

    def tag(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        self._stop_guard.watch(cancel_token)
        try:
            self._run(paths, on_event, cancel_token)
        finally:
            self._finder.clear_cache()

    def _run(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None:
        try:
            plan = plan_tracks(paths, self._list_album_files)
        except OSError as error:
            on_event(TaggingFailed(str(error)))
            return
        run = BatchRun(on_event, cancel_token, count_tracks(plan))
        on_event(TaggingStarted(count_tracks(plan)))
        self._process_plan(plan, run)
        on_event(run.make_finished())

    # Any file of an album folder brings in the whole album, so its tags stay alike.
    def _process_plan(self, plan: TrackPlan, run: BatchRun) -> None:
        for unit in plan.albums:
            if not self._process_album(unit, run):
                return
        singles = [AlbumTrack(path, None) for path in plan.singles]
        run.process(singles, lambda track: self._singles.tag(track.path))

    def _process_album(self, unit: AlbumUnit, run: BatchRun) -> bool:
        supplier = AlbumSupplier(self._albums, unit)
        return run.process(unit.tracks, lambda track: self._album_tracks.tag(track, supplier.get))
