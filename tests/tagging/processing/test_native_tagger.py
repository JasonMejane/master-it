from pathlib import Path

from masterit.cancellation import CancelToken
from masterit.library.audio_files import list_audio_files
from masterit.tagging.events import (
    AutoTagStatus,
    FileAutoTagged,
    TaggerEvent,
    TaggingFailed,
    TaggingFinished,
    TaggingStarted,
)
from masterit.tagging.metadata.types import (
    AlbumData,
    AlbumSearch,
    ExistingTags,
    TrackInfo,
    TrackMetadata,
)
from masterit.tagging.processing.native_tagger import NativeTagger
from masterit.tagging.track_tags import TrackTagStore

from ...tags.fixtures import copy_fixture
from .fakes import FakeAlbumFinder, FakeTagFiles, FakeTrackFinder

ARTIST = Path("/library/Queen")
JAZZ_FOLDER = ARTIST / "Queen - Jazz"
JAZZ_TRACKS = [JAZZ_FOLDER / "Queen - Mustapha.mp3", JAZZ_FOLDER / "Queen - Bicycle Race.mp3"]
SINGLE = ARTIST / "Queen - Radio Ga Ga.mp3"
JAZZ = AlbumData("Jazz", "Queen", "1978", "Rock", None, [], True)
FOUND = TrackMetadata(TrackInfo("Radio Ga Ga", "Queen", "The Works", "1984"))


class Run:
    def __init__(
        self,
        files: FakeTagFiles | None = None,
        album: AlbumData | Exception = JAZZ,
        listed: list[Path] | None = None,
    ) -> None:
        self.files = files or FakeTagFiles(
            {path: ExistingTags() for path in [*JAZZ_TRACKS, SINGLE]}
        )
        self.finder = FakeTrackFinder([FOUND])
        self.albums = FakeAlbumFinder(album)
        self.listed = JAZZ_TRACKS if listed is None else listed
        self.events: list[TaggerEvent] = []
        self.tagger = NativeTagger(
            self.finder, self.albums, self.files, lambda _folder: self.listed
        )

    def tag(self, paths: list[Path], token: CancelToken | None = None) -> list[TaggerEvent]:
        self.tagger.tag(paths, self.events.append, token or CancelToken())
        return self.events


def make_file_event(path: Path, status: AutoTagStatus, reason: str = "") -> FileAutoTagged:
    return FileAutoTagged(path, status, reason)


def test_tags_albums_from_one_lookup_then_singles_and_reports_each_file():
    run = Run()
    events = run.tag([JAZZ_TRACKS[0], SINGLE])
    assert events == [
        TaggingStarted(3),
        make_file_event(JAZZ_TRACKS[0], AutoTagStatus.TAGGED),
        make_file_event(JAZZ_TRACKS[1], AutoTagStatus.TAGGED),
        make_file_event(SINGLE, AutoTagStatus.TAGGED),
        TaggingFinished(tagged=3, skipped=0, failed=0, unprocessed=0, stopped=False),
    ]
    assert run.albums.searches == [(AlbumSearch("Queen", "Jazz"), 2)]
    assert run.finder.clears == 1


def test_reports_skipped_files_with_their_reason():
    run = Run()
    run.finder.results = [None]
    events = run.tag([SINGLE])
    assert events[1] == make_file_event(SINGLE, AutoTagStatus.SKIPPED, "not found")
    assert events[-1] == TaggingFinished(
        tagged=0, skipped=1, failed=0, unprocessed=0, stopped=False
    )


def test_fails_a_file_with_its_error_and_goes_on():
    run = Run(FakeTagFiles({SINGLE: ExistingTags()}), listed=[])
    broken = ARTIST / "broken.wav"
    events = run.tag([broken, SINGLE])
    assert events[1] == make_file_event(
        broken, AutoTagStatus.FAILED, "Tags not supported for broken.wav"
    )
    assert events[2] == make_file_event(SINGLE, AutoTagStatus.TAGGED)


def test_fails_the_tracks_of_an_album_it_cannot_look_up_once_and_goes_on():
    run = Run(album=RuntimeError("resolver bug"))
    events = run.tag([*JAZZ_TRACKS, SINGLE])
    statuses = [event.status for event in events if isinstance(event, FileAutoTagged)]
    assert statuses == [AutoTagStatus.FAILED, AutoTagStatus.FAILED, AutoTagStatus.TAGGED]
    assert len(run.albums.searches) == 1
    assert events[1] == make_file_event(JAZZ_TRACKS[0], AutoTagStatus.FAILED, "resolver bug")
    assert events[2] == make_file_event(JAZZ_TRACKS[1], AutoTagStatus.FAILED, "resolver bug")


def test_names_an_error_without_message_by_its_type():
    run = Run(album=RuntimeError())
    events = run.tag(JAZZ_TRACKS[:1])
    assert events[1] == make_file_event(JAZZ_TRACKS[0], AutoTagStatus.FAILED, "RuntimeError")


def test_looks_no_further_album_up_once_stopped_between_albums():
    other = ARTIST / "Queen - Innuendo" / "Queen - Bicycle.mp3"
    files = FakeTagFiles({path: ExistingTags() for path in [*JAZZ_TRACKS, other]})
    token = CancelToken()
    run = Run(files, listed=[])

    def stop_after_first_album(event: TaggerEvent) -> None:
        run.events.append(event)
        if event == make_file_event(JAZZ_TRACKS[1], AutoTagStatus.TAGGED):
            token.cancel()

    run.listed = []
    run.tagger = NativeTagger(
        run.finder,
        run.albums,
        run.files,
        lambda folder: [path for path in [*JAZZ_TRACKS, other] if path.parent == folder],
    )
    run.tagger.tag([*JAZZ_TRACKS, other], stop_after_first_album, token)
    assert [search.album for search, _count in run.albums.searches] == ["Jazz"]


def test_counts_the_files_of_an_album_holding_disc_folders():
    tracks = [JAZZ_FOLDER / "CD1" / "a.mp3", JAZZ_FOLDER / "CD2" / "b.mp3"]
    run = Run(FakeTagFiles({path: ExistingTags() for path in tracks}), listed=tracks)
    run.tag(tracks[:1])
    assert run.albums.searches == [(AlbumSearch("Queen", "Jazz"), 2)]


def test_stops_before_the_next_file_once_a_stop_is_requested():
    token = CancelToken()
    run = Run()
    run.tagger.tag(
        [*JAZZ_TRACKS, SINGLE], lambda event: stop_after_first_file(event, token, run), token
    )
    assert run.events[-1] == TaggingFinished(
        tagged=1, skipped=0, failed=0, unprocessed=2, stopped=True
    )
    assert run.finder.calls == []


def stop_after_first_file(event: TaggerEvent, token: CancelToken, run: Run) -> None:
    run.events.append(event)
    if isinstance(event, FileAutoTagged):
        token.cancel()


def test_looks_no_album_up_once_stopped():
    token = CancelToken()
    token.cancel()
    run = Run()
    events = run.tag(JAZZ_TRACKS, token)
    assert events == [TaggingStarted(2), TaggingFinished(0, 0, 0, 2, True)]
    assert run.albums.searches == []


def test_fits_no_tracklist_to_a_sibling_disc_folder():
    disc_folder = ARTIST / "Queen - Live Killers - CD2"
    tracks = [disc_folder / "a.mp3", disc_folder / "b.mp3"]
    run = Run(FakeTagFiles({path: ExistingTags() for path in tracks}), listed=tracks)
    run.tag(tracks[:1])
    assert run.albums.searches == [(AlbumSearch("Queen", "Live Killers"), None)]


def test_fails_the_run_when_an_album_folder_cannot_be_listed():
    run = Run()

    def fail(_folder: Path) -> list[Path]:
        raise OSError("folder gone")

    run.tagger = NativeTagger(run.finder, run.albums, run.files, fail)
    assert run.tag(JAZZ_TRACKS) == [TaggingFailed("folder gone")]
    assert run.finder.clears == 1


def test_tags_real_files_of_an_album_and_a_single(tmp_path: Path):
    album_folder = tmp_path / "Queen" / "Queen - Jazz"
    album_folder.mkdir(parents=True)
    album_song = copy_fixture(album_folder, "flac", "Queen - Mustapha")
    single = copy_fixture(tmp_path / "Queen", "mp3", "Queen - Radio Ga Ga")
    jazz = AlbumData("Jazz", "Queen", "1978", "Rock", b"\xff\xd8\xffcover", [], True)
    tagger = NativeTagger(
        FakeTrackFinder([FOUND]), FakeAlbumFinder(jazz), TrackTagStore(), list_audio_files
    )
    events: list[TaggerEvent] = []
    tagger.tag([album_song, single], events.append, CancelToken())
    assert events[-1] == TaggingFinished(
        tagged=2, skipped=0, failed=0, unprocessed=0, stopped=False
    )
    store = TrackTagStore()
    assert store.read(album_song).info == TrackInfo("Mustapha", "Queen", "Jazz", "1978")
    assert store.read_cover(album_song) == b"\xff\xd8\xffcover"
    assert store.read(single).info == FOUND.info
