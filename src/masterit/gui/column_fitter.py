from collections.abc import Set as AbstractSet
from typing import override

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QTableView

WIDE_FACTOR = 2


def get_fitted_widths(widths: list[int], available: int) -> list[int]:
    total = sum(widths)
    if not total:
        return widths
    fitted = [width * available // total for width in widths]
    fitted[-1] += available - sum(fitted)
    return fitted


def get_starting_widths(
    header_widths: list[int], wide_columns: AbstractSet[int], base: int
) -> list[int]:
    return [
        base * WIDE_FACTOR if column in wide_columns else max(base, header_width)
        for column, header_width in enumerate(header_widths)
    ]


def get_shifted_widths(widths: list[int], column: int, new_width: int, minimum: int) -> list[int]:
    following = column + 1
    if following >= len(widths):
        return widths
    pair = widths[column] + widths[following]
    width = min(max(new_width, minimum), pair - minimum)
    shifted = list(widths)
    shifted[column], shifted[following] = width, pair - width
    return shifted


class ColumnFitter(QObject):
    """Keeps a table's columns filling its width; a drag trades width with the next column."""

    def __init__(self, view: QTableView, wide_columns: AbstractSet[int] = frozenset()) -> None:
        super().__init__(view)
        self._header = view.horizontalHeader()
        self._viewport = view.viewport()
        self._wide_columns = wide_columns
        self._is_fitting = False
        # Fitting from live sizes would lose proportions to rounding at tiny widths.
        self._target_widths = self._get_starting_widths()
        self._apply_widths(self._target_widths)
        self._header.sectionResized.connect(self._share_resize_with_next)
        self._header.sectionCountChanged.connect(self._restart_targets)
        self._viewport.installEventFilter(self)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize:
            self.fit_columns()
        return False

    def fit_columns(self) -> None:
        self._apply_widths(get_fitted_widths(self._target_widths, self._viewport.width()))

    def _get_starting_widths(self) -> list[int]:
        hints = [self._header.sectionSizeHint(column) for column in range(self._header.count())]
        return get_starting_widths(hints, self._wide_columns, self._header.defaultSectionSize())

    def _get_live_widths(self) -> list[int]:
        return [self._header.sectionSize(column) for column in range(self._header.count())]

    def _apply_widths(self, widths: list[int]) -> None:
        self._is_fitting = True
        for column, width in enumerate(widths):
            self._header.resizeSection(column, width)
        self._is_fitting = False

    def _share_resize_with_next(self, column: int, old_width: int, new_width: int) -> None:
        if self._is_fitting:
            return
        widths = self._get_live_widths()
        widths[column] = old_width
        shifted = get_shifted_widths(widths, column, new_width, self._header.minimumSectionSize())
        self._apply_widths(shifted)
        if shifted[column] != old_width:
            self._update_targets(column, shifted)

    def _update_targets(self, column: int, live_widths: list[int]) -> None:
        # Split by the live pair only: other live columns may be clamped wider than their share.
        live_pair = live_widths[column] + live_widths[column + 1]
        target_pair = self._target_widths[column] + self._target_widths[column + 1]
        target = round(target_pair * live_widths[column] / live_pair)
        self._target_widths = get_shifted_widths(self._target_widths, column, target, 0)

    def _restart_targets(self) -> None:
        self._target_widths = self._get_starting_widths()
        self.fit_columns()
