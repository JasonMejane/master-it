from pathlib import Path

AUDIO_EXTENSIONS = frozenset({".mp3", ".opus", ".m4a", ".flac", ".ogg", ".wav"})


def list_audio_files(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if is_visible_audio_file(path, folder))


def is_visible_audio_file(path: Path, folder: Path) -> bool:
    is_hidden = any(part.startswith(".") for part in path.relative_to(folder).parts)
    return not is_hidden and path.suffix.lower() in AUDIO_EXTENSIONS and path.is_file()
