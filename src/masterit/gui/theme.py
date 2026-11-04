from dataclasses import asdict, dataclass
from functools import partial
from importlib.resources import files
from pathlib import Path
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

Role = QPalette.ColorRole


@dataclass(frozen=True)
class ThemeTokens:
    window: str
    surface: str
    field: str
    alternate: str
    border: str
    hover: str
    text: str
    muted: str
    link: str
    danger: str
    accent: str = "#2f78b5"
    accent_hover: str = "#28699f"
    accent_pressed: str = "#225a88"
    accent_text: str = "#ffffff"


DARK_TOKENS = ThemeTokens(
    window="#1d2025",
    surface="#262a30",
    field="#1a1d21",
    alternate="#22262b",
    border="#3a3f47",
    hover="#323840",
    text="#e4e7eb",
    muted="#8d95a0",
    link="#6aaee6",
    danger="#f07178",
)
LIGHT_TOKENS = ThemeTokens(
    window="#eef0f3",
    surface="#ffffff",
    field="#ffffff",
    alternate="#f5f7f9",
    border="#d3d8de",
    hover="#e6e9ed",
    text="#1f2328",
    muted="#6b7380",
    link="#2f78b5",
    danger="#c62828",
)
PALETTE_TOKENS = {
    Role.Window: "window",
    Role.WindowText: "text",
    Role.Base: "field",
    Role.AlternateBase: "alternate",
    Role.Text: "text",
    Role.Button: "surface",
    Role.ButtonText: "text",
    Role.PlaceholderText: "muted",
    Role.Highlight: "accent",
    Role.HighlightedText: "accent_text",
    Role.ToolTipBase: "surface",
    Role.ToolTipText: "text",
    Role.Link: "link",
    Role.Accent: "accent",
    Role.BrightText: "accent_text",
}
# Qt bevels expect Light > Midlight > Button > Mid > Dark > Shadow.
SHADE_FACTORS = {Role.Light: 150, Role.Midlight: 120, Role.Mid: 80, Role.Dark: 55}
SHADOW_COLOR = "#000000"
THEME_FILES = files("masterit.gui")
DIMMED_ROLES = (Role.WindowText, Role.Text, Role.ButtonText)


def get_theme_tokens(scheme: Qt.ColorScheme) -> ThemeTokens:
    return DARK_TOKENS if scheme == Qt.ColorScheme.Dark else LIGHT_TOKENS


@dataclass
class ActiveTheme:
    tokens: ThemeTokens = LIGHT_TOKENS


ACTIVE_THEME = ActiveTheme()


def get_active_tokens() -> ThemeTokens:
    return ACTIVE_THEME.tokens


def make_stylesheet(tokens: ThemeTokens) -> str:
    template = THEME_FILES.joinpath("style.qss").read_text(encoding="utf-8")
    return Template(template).substitute(
        asdict(tokens),
        combo_arrow=get_theme_file_path("combo-arrow.svg"),
        check_mark=get_theme_file_path("check-mark.svg"),
    )


def get_theme_file_path(name: str) -> str:
    return Path(str(THEME_FILES.joinpath(name))).as_posix()


def make_palette(tokens: ThemeTokens) -> QPalette:
    palette = QPalette()
    values = asdict(tokens)
    for role, token in PALETTE_TOKENS.items():
        palette.setColor(role, QColor(values[token]))
    set_shades(palette, QColor(tokens.surface))
    for role in DIMMED_ROLES:
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(tokens.muted))
    return palette


def set_shades(palette: QPalette, button: QColor) -> None:
    for role, factor in SHADE_FACTORS.items():
        palette.setColor(role, button.lighter(factor))
    palette.setColor(Role.Shadow, QColor(SHADOW_COLOR))


def apply_theme(app: QApplication, scheme: Qt.ColorScheme) -> None:
    tokens = get_theme_tokens(scheme)
    ACTIVE_THEME.tokens = tokens
    app.setPalette(make_palette(tokens))
    app.setStyleSheet(make_stylesheet(tokens))


def follow_system_theme(app: QApplication) -> None:
    hints = app.styleHints()
    apply_theme(app, hints.colorScheme())
    hints.colorSchemeChanged.connect(partial(apply_theme, app))
