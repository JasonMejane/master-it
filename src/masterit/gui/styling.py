from typing import cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QFrame, QLabel, QLayout, QPushButton, QVBoxLayout, QWidget

from masterit.gui.icons import get_icon

BUTTON_ICON_SIZE = QSize(20, 16)


def make_card(content: QWidget | QLayout) -> QFrame:
    card = QFrame()
    card.setObjectName("section")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(8, 6, 8, 8)
    layout.setSpacing(4)
    if isinstance(content, QLayout):
        layout.addLayout(content)
    else:
        layout.addWidget(content, stretch=1)
    return card


def make_section(title: str, content: QWidget | QLayout) -> QFrame:
    section = make_card(content)
    title_label = QLabel(title)
    title_label.setObjectName("sectionTitle")
    if isinstance(content, QWidget):
        title_label.setBuddy(content)
    cast(QVBoxLayout, section.layout()).insertWidget(0, title_label)
    return section


def make_button(text: str, icon_name: str) -> QPushButton:
    return make_icon_button(text, get_icon(icon_name))


def make_primary_button(text: str, icon_name: str) -> QPushButton:
    button = make_icon_button(text, get_icon(icon_name, QPalette.ColorRole.HighlightedText))
    button.setProperty("role", "primary")
    return button


def make_icon_button(text: str, icon: QIcon) -> QPushButton:
    button = QPushButton(icon, text)
    button.setIconSize(BUTTON_ICON_SIZE)
    return button


def mark_muted(label: QLabel) -> None:
    label.setProperty("muted", True)
