from collections.abc import Iterator

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from masterit.gui import icons
from masterit.gui.icons import ICON_NAMES, get_icon

Role = QPalette.ColorRole
ICON_SIZE = QSize(24, 24)


@pytest.fixture
def known_palette(qapp: QApplication) -> Iterator[QPalette]:
    original = qapp.palette()
    palette = QPalette()
    palette.setColor(Role.ButtonText, QColor("#112233"))
    palette.setColor(QPalette.ColorGroup.Disabled, Role.ButtonText, QColor("#445566"))
    palette.setColor(Role.HighlightedText, QColor("#778899"))
    qapp.setPalette(palette)
    yield palette
    qapp.setPalette(original)


def get_drawn_colors(icon: QIcon, mode: QIcon.Mode = QIcon.Mode.Normal) -> set[str]:
    image = icon.pixmap(ICON_SIZE, mode).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return {pixel.name() for pixel in pixels if pixel.alpha() == 255}


@pytest.mark.parametrize("name", ICON_NAMES)
def test_every_bundled_icon_draws_something(qapp: QApplication, name: str):
    assert get_drawn_colors(get_icon(name))


def test_unknown_icon_is_rejected():
    with pytest.raises(FileNotFoundError):
        get_icon("missing")


def test_icon_takes_the_button_text_color(known_palette: QPalette):
    assert get_drawn_colors(get_icon("check")) == {"#112233"}


def test_disabled_icon_takes_the_disabled_color(known_palette: QPalette):
    assert get_drawn_colors(get_icon("check"), QIcon.Mode.Disabled) == {"#445566"}


def test_icon_can_use_another_palette_role(known_palette: QPalette):
    assert get_drawn_colors(get_icon("check", Role.HighlightedText)) == {"#778899"}


def test_disabled_icon_ignores_its_role(known_palette: QPalette):
    icon = get_icon("check", Role.HighlightedText)
    assert get_drawn_colors(icon, QIcon.Mode.Disabled) == {"#445566"}


def test_icon_copies_keep_drawing_in_palette_color(known_palette: QPalette):
    icon = get_icon("check")
    copy = QIcon(icon)
    copy.addPixmap(QPixmap(1, 1), QIcon.Mode.Selected)
    assert get_drawn_colors(copy) == {"#112233"}


def test_selected_icon_takes_the_highlighted_text_color(known_palette: QPalette):
    assert get_drawn_colors(get_icon("check"), QIcon.Mode.Selected) == {"#778899"}


def test_wide_sizes_keep_the_glyph_square_and_leave_room_after_it(qapp: QApplication):
    image = get_icon("check").pixmap(QSize(48, 16)).toImage()
    columns = range(image.width())
    drawn = [x for x in columns if any(image.pixelColor(x, y).alpha() for y in range(16))]
    assert max(drawn) < 16


def test_icon_follows_palette_changes(qapp: QApplication, known_palette: QPalette):
    icon = get_icon("check")
    get_drawn_colors(icon)
    known_palette.setColor(Role.ButtonText, QColor("#aabbcc"))
    qapp.setPalette(known_palette)
    assert get_drawn_colors(icon) == {"#aabbcc"}


def test_engines_of_deleted_icon_copies_are_released(qapp: QApplication):
    for _ in range(3):
        copy = QIcon(get_icon("check"))
        copy.addPixmap(QPixmap(1, 1), QIcon.Mode.Selected)
        del copy
    assert len(icons.cloned_engines) == 1


def test_tall_sizes_center_the_glyph_vertically(qapp: QApplication):
    image = get_icon("check").pixmap(QSize(16, 48)).toImage()
    rows = range(image.height())
    drawn = [y for y in rows if any(image.pixelColor(x, y).alpha() for x in range(16))]
    assert min(drawn) >= 16
    assert max(drawn) < 32
