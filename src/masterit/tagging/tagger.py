from pathlib import Path
from typing import Protocol

from masterit.cancellation import CancelToken
from masterit.tagging.events import TaggerEventHandler


class Tagger(Protocol):
    def tag(
        self, paths: list[Path], on_event: TaggerEventHandler, cancel_token: CancelToken
    ) -> None: ...
