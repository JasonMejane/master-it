import threading


class SkipList:
    """Items the user chose to skip; the GUI writes it while the download thread reads it."""

    def __init__(self) -> None:
        self._skipped: set[tuple[str, str | None]] = set()
        self._lock = threading.Lock()

    def set_skipped(self, source_url: str, item_id: str | None, skipped: bool) -> None:
        with self._lock:
            if skipped:
                self._skipped.add((source_url, item_id))
            else:
                self._skipped.discard((source_url, item_id))

    def is_skipped(self, source_url: str, item_id: str | None) -> bool:
        with self._lock:
            return (source_url, item_id) in self._skipped
