import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QStandardItemModel
from PySide6.QtWidgets import QApplication, QTableView, QWidget
from pytestqt.qtbot import QtBot

from masterit.gui.column_fitter import (
    ColumnFitter,
    get_fitted_widths,
    get_shifted_widths,
    get_starting_widths,
)


@pytest.mark.parametrize(
    ("widths", "available", "fitted"),
    [
        ([100, 100, 200], 800, [200, 200, 400]),
        ([100, 100, 200], 200, [50, 50, 100]),
        ([1, 1, 1], 10, [3, 3, 4]),
        ([0, 0], 100, [0, 0]),
        ([], 100, []),
    ],
)
def test_widths_are_scaled_to_fill_the_space(widths: list[int], available: int, fitted: list[int]):
    assert get_fitted_widths(widths, available) == fitted


@pytest.mark.parametrize(
    ("widths", "column", "new_width", "shifted"),
    [
        ([100, 100, 100], 0, 150, [150, 50, 100]),
        ([100, 100, 100], 1, 60, [100, 60, 140]),
        ([100, 100, 100], 0, 500, [170, 30, 100]),
        ([100, 100, 100], 0, 10, [30, 170, 100]),
        ([100, 100, 100], 2, 150, [100, 100, 100]),
    ],
)
def test_width_moves_between_a_column_and_the_next(
    widths: list[int], column: int, new_width: int, shifted: list[int]
):
    assert get_shifted_widths(widths, column, new_width, minimum=30) == shifted


def test_wide_columns_start_twice_the_base_and_others_fit_their_header():
    assert get_starting_widths([40, 150, 60], {0}, 100) == [200, 150, 100]


def test_fitter_applies_starting_widths_before_filling(qtbot: QtBot):
    view = QTableView()
    view.setModel(QStandardItemModel(1, 3, view))
    qtbot.addWidget(view)
    ColumnFitter(view, wide_columns={0})
    first, second, third = get_column_widths(view)
    assert first == 2 * second
    assert second == third


def make_fitted_view(qtbot: QtBot, columns: int = 4) -> QTableView:
    view = QTableView()
    view.setModel(QStandardItemModel(3, columns, view))
    ColumnFitter(view)
    qtbot.addWidget(view)
    view.resize(600, 300)
    view.show()
    qtbot.waitExposed(view)
    return view


def get_column_widths(view: QTableView) -> list[int]:
    header = view.horizontalHeader()
    return [header.sectionSize(column) for column in range(header.count())]


def test_columns_fill_the_view(qtbot: QtBot):
    view = make_fitted_view(qtbot)
    qtbot.waitUntil(lambda: sum(get_column_widths(view)) == view.viewport().width())
    assert not view.horizontalScrollBar().isVisible()


def wait_until_filled(qtbot: QtBot, view: QTableView) -> None:
    qtbot.waitUntil(lambda: sum(get_column_widths(view)) == view.viewport().width())


def test_resizing_the_view_keeps_user_proportions(qtbot: QtBot):
    view = make_fitted_view(qtbot, columns=2)
    wait_until_filled(qtbot, view)
    view.horizontalHeader().resizeSection(0, view.viewport().width() * 3 // 4)
    view.resize(1000, 300)
    wait_until_filled(qtbot, view)
    first, second = get_column_widths(view)
    assert first == pytest.approx(3 * second, abs=2)


def drag_column_border(view: QTableView, column: int, distance: int) -> None:
    header = view.horizontalHeader()
    border = QPoint(header.sectionViewportPosition(column) + header.sectionSize(column) - 1, 5)
    target = border + QPoint(distance, 0)
    viewport = header.viewport()
    left = Qt.MouseButton.LeftButton
    send_mouse(viewport, QEvent.Type.MouseButtonPress, border, left)
    send_mouse(viewport, QEvent.Type.MouseMove, target, left)
    send_mouse(viewport, QEvent.Type.MouseButtonRelease, target, Qt.MouseButton.NoButton)


def send_mouse(widget: QWidget, kind: QEvent.Type, position: QPoint, buttons: Qt.MouseButton):
    global_position = QPointF(widget.mapToGlobal(position))
    event = QMouseEvent(
        kind,
        QPointF(position),
        global_position,
        Qt.MouseButton.LeftButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(widget, event)


@pytest.mark.parametrize("distance", [60, -40])
def test_dragging_a_border_moves_width_to_the_next_column_only(qtbot: QtBot, distance: int):
    view = make_fitted_view(qtbot)
    wait_until_filled(qtbot, view)
    before = get_column_widths(view)
    drag_column_border(view, 1, distance)
    after = get_column_widths(view)
    assert after[1] == before[1] + distance
    assert after[2] == before[2] - distance
    assert [after[0], after[3]] == [before[0], before[3]]
    assert sum(after) == view.viewport().width()


def test_next_column_keeps_its_minimum_width(qtbot: QtBot):
    view = make_fitted_view(qtbot)
    wait_until_filled(qtbot, view)
    before = get_column_widths(view)
    view.horizontalHeader().resizeSection(0, before[0] + 1000)
    after = get_column_widths(view)
    assert after[1] == view.horizontalHeader().minimumSectionSize()
    assert sum(after) == view.viewport().width()


def test_last_column_border_cannot_be_moved(qtbot: QtBot):
    view = make_fitted_view(qtbot)
    wait_until_filled(qtbot, view)
    before = get_column_widths(view)
    view.horizontalHeader().resizeSection(3, before[3] + 50)
    assert get_column_widths(view) == before


def test_added_columns_are_fitted_too(qtbot: QtBot):
    view = make_fitted_view(qtbot)
    wait_until_filled(qtbot, view)
    model = view.model()
    assert isinstance(model, QStandardItemModel)
    model.setColumnCount(6)
    wait_until_filled(qtbot, view)
    assert all(width > 0 for width in get_column_widths(view))


def test_proportions_survive_a_view_too_narrow_for_them(qtbot: QtBot):
    view = QTableView()
    view.setModel(QStandardItemModel(1, 3, view))
    qtbot.addWidget(view)
    ColumnFitter(view, wide_columns={0})
    view.show()
    view.resize(60, 100)
    qtbot.waitUntil(lambda: view.viewport().width() < 60)
    view.resize(900, 100)
    qtbot.waitUntil(lambda: sum(get_column_widths(view)) == view.viewport().width())
    first, second, _ = get_column_widths(view)
    assert first == pytest.approx(2 * second, abs=2)


def test_a_blocked_drag_in_a_narrow_view_keeps_the_proportions(qtbot: QtBot):
    view = QTableView()
    view.setModel(QStandardItemModel(1, 4, view))
    qtbot.addWidget(view)
    ColumnFitter(view, wide_columns={0})
    view.show()
    view.resize(80, 100)
    qtbot.waitUntil(lambda: view.viewport().width() < 80)
    header = view.horizontalHeader()
    header.resizeSection(0, header.sectionSize(0) + 5)
    view.resize(900, 100)
    wait_until_filled(qtbot, view)
    first, second, _, _ = get_column_widths(view)
    assert first == pytest.approx(2 * second, abs=2)
