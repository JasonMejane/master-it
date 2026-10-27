from pathlib import Path
from typing import Any, cast

import pytest
from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.metadataparser import (  # pyright: ignore[reportMissingTypeStubs]
    MetadataParserPP,
)

from masterit.download.options import make_ydl_options
from masterit.download.settings import AudioCodec, DownloadSettings

OUTPUT_DIR = Path("/music/yt")


class SilentCallbacks:
    def match_filter(self, info: dict[str, Any], *, incomplete: bool) -> None: ...
    def on_progress(self, status: dict[str, Any]) -> None: ...
    def on_postprocess(self, status: dict[str, Any]) -> None: ...
    def on_file_ready(self, file_path: str) -> None: ...
    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


CALLBACKS = SilentCallbacks()


def make_options(settings: DownloadSettings | None = None) -> dict[str, Any]:
    return make_ydl_options(settings or DownloadSettings(OUTPUT_DIR), CALLBACKS)


def get_postprocessor(options: dict[str, Any], key: str) -> dict[str, Any]:
    return next(pp for pp in options["postprocessors"] if pp["key"] == key)


def make_silent_ydl() -> YoutubeDL:
    return YoutubeDL(cast(Any, {"logger": CALLBACKS}))


def parse_metadata(info: dict[str, Any]) -> dict[str, Any]:
    actions = get_postprocessor(make_options(), "MetadataParser")["actions"]
    with make_silent_ydl() as ydl:
        parser: Any = MetadataParserPP(ydl, actions)
        return parser.run(info)[1]


def test_default_settings_extract_mp3_192():
    extract = get_postprocessor(make_options(), "FFmpegExtractAudio")
    assert (extract["preferredcodec"], extract["preferredquality"]) == ("mp3", "192")


def test_codec_and_quality_come_from_settings():
    settings = DownloadSettings(OUTPUT_DIR, codec=AudioCodec.OPUS, quality="5")
    extract = get_postprocessor(make_options(settings), "FFmpegExtractAudio")
    assert (extract["preferredcodec"], extract["preferredquality"]) == ("opus", "5")


def test_postprocessors_run_in_reference_script_order():
    keys = [pp["key"] for pp in make_options()["postprocessors"]]
    assert keys == [
        "MetadataParser",
        "FFmpegThumbnailsConvertor",
        "FFmpegExtractAudio",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]


def test_callbacks_are_wired():
    options = make_options()
    assert options["match_filter"] == CALLBACKS.match_filter
    assert options["progress_hooks"] == [CALLBACKS.on_progress]
    assert options["postprocessor_hooks"] == [CALLBACKS.on_postprocess]
    assert options["post_hooks"] == [CALLBACKS.on_file_ready]
    assert options["logger"] is CALLBACKS


def test_logged_messages_have_no_color_codes():
    assert make_options()["color"] == "never"


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"title": "Artist - Song", "artist": None}, "/music/yt/Artist - Song.mp3"),
        ({"title": "Song"}, "/music/yt/Song.mp3"),
    ],
)
def test_file_name_starts_with_artist_when_known(info: dict[str, Any], expected: str):
    template = make_options()["outtmpl"]["default"]
    parsed = parse_metadata({**info, "ext": "mp3"})
    with make_silent_ydl() as ydl:
        assert ydl.evaluate_outtmpl(template, cast(Any, parsed)) == expected


def test_playlist_items_go_to_playlist_folder():
    assert make_options()["outtmpl"]["playlist"].startswith("/music/yt/%(playlist_title)s/")


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Song (Official Video)", "Song"),
        ("Song [Lyric Video]", "Song"),
        ("Song (Clip Officiel)  extra", "Song extra"),
        ("Song (OFFICIAL MUSIC VIDEO)", "Song"),
    ],
)
def test_title_noise_is_removed(title: str, expected: str):
    assert parse_metadata({"title": title})["title"] == expected


@pytest.mark.parametrize("separator", ["-", "\u2013", "\u2014"])
def test_artist_is_split_from_title(separator: str):
    parsed = parse_metadata({"title": f"Daft Punk {separator} One More Time (Official Video)"})
    assert (parsed["artist"], parsed["title"]) == ("Daft Punk", "One More Time")


def test_title_is_not_split_when_artist_is_known():
    parsed = parse_metadata({"title": "Intro - Remastered 2009", "artist": "The Beatles"})
    assert (parsed["artist"], parsed["title"]) == ("The Beatles", "Intro - Remastered 2009")


def test_title_without_separator_keeps_existing_artist():
    parsed = parse_metadata({"title": "One More Time", "artist": "Daft Punk"})
    assert (parsed["artist"], parsed["title"]) == ("Daft Punk", "One More Time")


@pytest.mark.parametrize(
    ("uploader", "expected"),
    [
        ("Daft Punk - Topic", "Daft Punk"),
        ("DaftPunkVEVO", "DaftPunk"),
        ("DaftPunkVevo", "DaftPunk"),
    ],
)
def test_channel_suffixes_are_removed_from_uploader(uploader: str, expected: str):
    assert parse_metadata({"title": "Song", "uploader": uploader})["uploader"] == expected
