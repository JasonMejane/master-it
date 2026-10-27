import shutil
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures"
FORMATS = ("mp3", "flac", "opus", "ogg", "m4a")


def copy_fixture(
    folder: Path, extension: str, name: str = "song", fixture: str = "silence"
) -> Path:
    target = folder / f"{name}.{extension}"
    shutil.copyfile(FIXTURES / f"{fixture}.{extension}", target)
    return target
