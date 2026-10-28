import os
from pathlib import Path

from masterit.tagging.web.url_text import replace_lone_surrogates


# Undecodable bytes of a name read as U+FFFD, one per broken sequence, as Node reads them.
# Windows names hold UTF-16 instead, where only a lone surrogate is broken.
def make_readable_path(path: Path, system: str = os.name) -> Path:
    if system == "nt":
        return Path(replace_lone_surrogates(str(path)))
    return Path(os.fsencode(path).decode("utf-8", "replace"))
