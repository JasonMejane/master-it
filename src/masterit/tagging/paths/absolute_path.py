import os
from pathlib import Path, PurePath


# Collapses ".." without resolving symlinks, so names stay as the user sees them.
def make_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))  # noqa: PTH100 - pathlib has no lexical normalization


def get_relative_folders(folder: PurePath, root: PurePath) -> tuple[str, ...]:
    try:
        return folder.relative_to(root, walk_up=True).parts
    except ValueError:
        return folder.relative_to(folder.anchor).parts
