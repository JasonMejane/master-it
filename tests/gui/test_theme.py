import re
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QCheckBox
from pytestqt.qtbot import QtBot

from masterit.gui.theme import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    ThemeTokens,
    apply_theme,
    follow_system_theme,
    get_active_tokens,
    get_theme_tokens,
    make_palette,
    make_stylesheet,
)

Scheme = Qt.ColorScheme
Role = QPalette.ColorRole


@pytest.mark.parametrize(
    ("scheme", "tokens"),
    [(Scheme.Dark, DARK_TOKENS), (Scheme.Light, LIGHT_TOKENS), (Scheme.Unknown, LIGHT_TOKENS)],
)
def test_theme_tokens_follow_the_color_scheme(scheme: Qt.ColorScheme, tokens: ThemeTokens):
    assert get_theme_tokens(scheme) is tokens


def test_both_themes_share_an_accent_readable_under_white_text():
    assert DARK_TOKENS.accent == LIGHT_TOKENS.accent == "#2f78b5"


@pytest.mark.parametrize("tokens", [DARK_TOKENS, LIGHT_TOKENS])
def test_stylesheet_fills_every_token(tokens: ThemeTokens):
    stylesheet = make_stylesheet(tokens)
    assert "#2f78b5" in stylesheet
    assert "$" not in stylesheet


def test_palette_uses_theme_colors():
    palette = make_palette(DARK_TOKENS)
    assert palette.color(Role.Window) == QColor(DARK_TOKENS.window)
    assert palette.color(Role.Highlight) == QColor(DARK_TOKENS.accent)
    assert palette.color(Role.HighlightedText) == QColor(DARK_TOKENS.accent_text)


def test_palette_derives_secondary_roles_from_the_theme():
    palette = make_palette(DARK_TOKENS)
    assert palette.color(Role.Link) == QColor(DARK_TOKENS.link)
    assert palette.color(Role.Accent) == QColor(DARK_TOKENS.accent)


def test_active_tokens_are_the_applied_theme(qapp: QApplication):
    apply_theme(qapp, Scheme.Dark)
    assert get_active_tokens() is DARK_TOKENS
    apply_theme(qapp, Scheme.Light)
    assert get_active_tokens() is LIGHT_TOKENS


@pytest.mark.parametrize("tokens", [DARK_TOKENS, LIGHT_TOKENS])
def test_palette_shades_go_from_light_to_shadow(tokens: ThemeTokens):
    palette = make_palette(tokens)
    shades = (Role.Light, Role.Midlight, Role.Button, Role.Mid, Role.Dark, Role.Shadow)
    lightness = [palette.color(role).lightness() for role in shades]
    assert lightness == sorted(lightness, reverse=True)
    assert len(set(lightness[2:])) == len(shades) - 2


def test_checked_boxes_stay_outlined_in_selected_rows():
    assert "QAbstractItemView::indicator:checked:selected" in make_stylesheet(DARK_TOKENS)


def test_palette_dims_disabled_text():
    palette = make_palette(LIGHT_TOKENS)
    disabled = QPalette.ColorGroup.Disabled
    for role in (Role.Text, Role.WindowText, Role.ButtonText):
        assert palette.color(disabled, role) == QColor(LIGHT_TOKENS.muted)


def test_apply_theme_sets_stylesheet_and_palette(qapp: QApplication):
    apply_theme(qapp, Scheme.Dark)
    assert qapp.styleSheet() == make_stylesheet(DARK_TOKENS)
    assert qapp.palette().color(Role.Window) == QColor(DARK_TOKENS.window)


def test_theme_starts_from_the_system_scheme(qapp: QApplication):
    follow_system_theme(qapp)
    scheme = qapp.styleHints().colorScheme()
    assert qapp.styleSheet() == make_stylesheet(get_theme_tokens(scheme))


def test_theme_follows_system_scheme_changes(qapp: QApplication):
    follow_system_theme(qapp)
    qapp.styleHints().colorSchemeChanged.emit(Scheme.Dark)
    assert qapp.styleSheet() == make_stylesheet(DARK_TOKENS)
    qapp.styleHints().colorSchemeChanged.emit(Scheme.Light)
    assert qapp.styleSheet() == make_stylesheet(LIGHT_TOKENS)


def test_stylesheet_images_are_bundled_files():
    image_paths = re.findall(r"image: url\(([^)]+)\)", make_stylesheet(DARK_TOKENS))
    assert len(image_paths) == 2
    assert all(Path(path).is_file() for path in image_paths)


def test_dark_checkbox_outline_stands_out(qtbot: QtBot, qapp: QApplication):
    apply_theme(qapp, Scheme.Dark)
    checkbox = QCheckBox()
    qtbot.addWidget(checkbox)
    checkbox.show()
    image = checkbox.grab().toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    assert DARK_TOKENS.muted in {pixel.name() for pixel in pixels}
