from pathlib import Path
from typing import Any, Protocol

from yt_dlp.postprocessor.metadataparser import (  # pyright: ignore[reportMissingTypeStubs]
    MetadataParserPP,
)

from masterit.download.settings import DownloadSettings

TITLE_NOISE_PATTERNS = (
    r"(?i)[\[\(]lyric\s+video[\]\)]",
    r"(?i)[\[\(](official\s+video|official\s+lyric\s+video|official\s+music\s+video"
    r"|official\s+visualiser|clip\s+officiel|vidéoclip\s+officiel)[\]\)]",
)
# The title is only split when yt-dlp found no artist: the template starts with the marker then.
SPLIT_MARKER = "\x1f"
ARTIST_TITLE_INPUT = f"%(artist|)s{SPLIT_MARKER}%(title)s"
ARTIST_TITLE_PATTERN = "^" + SPLIT_MARKER + r"(?P<artist>.+?)\s+[-\u2013\u2014]\s+(?P<title>.+)$"
CHANNEL_SUFFIX_PATTERN = r"(?i)\s*-\s*Topic$|VEVO$"
FILE_NAME_TEMPLATE = "%(artist&{} - |)s%(title)s.%(ext)s"


class YdlCallbacks(Protocol):
    def match_filter(self, info: dict[str, Any], *, incomplete: bool) -> str | None: ...
    def on_progress(self, status: dict[str, Any]) -> None: ...
    def on_postprocess(self, status: dict[str, Any]) -> None: ...
    def on_file_ready(self, file_path: str) -> None: ...
    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


def make_ydl_options(settings: DownloadSettings, callbacks: YdlCallbacks) -> dict[str, Any]:
    return {
        "format": "bestaudio/best",
        "postprocessors": [make_metadata_parser(), *make_audio_postprocessors(settings)],
        "writethumbnail": True,
        "outtmpl": make_output_templates(settings.output_dir),
        "ignoreerrors": True,
        "noprogress": True,
        "color": "never",
        "match_filter": callbacks.match_filter,
        "progress_hooks": [callbacks.on_progress],
        "postprocessor_hooks": [callbacks.on_postprocess],
        "post_hooks": [callbacks.on_file_ready],
        "logger": callbacks,
    }


def make_metadata_parser() -> dict[str, Any]:
    replace = MetadataParserPP.Actions.REPLACE
    return {
        "key": "MetadataParser",
        "when": "pre_process",
        "actions": [
            *((replace, "title", pattern, "") for pattern in TITLE_NOISE_PATTERNS),
            (replace, "title", r"\s+", " "),
            (replace, "title", r"^\s+|\s+$", ""),
            (MetadataParserPP.Actions.INTERPRET, ARTIST_TITLE_INPUT, ARTIST_TITLE_PATTERN),
            (replace, "uploader", CHANNEL_SUFFIX_PATTERN, ""),
        ],
    }


def make_audio_postprocessors(settings: DownloadSettings) -> list[dict[str, Any]]:
    return [
        {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": str(settings.codec),
            "preferredquality": settings.quality,
        },
        {"key": "FFmpegMetadata"},
        {"key": "EmbedThumbnail", "already_have_thumbnail": False},
    ]


def make_output_templates(output_dir: Path) -> dict[str, str]:
    return {
        "default": str(output_dir / FILE_NAME_TEMPLATE),
        "playlist": str(output_dir / "%(playlist_title)s" / FILE_NAME_TEMPLATE),
    }
