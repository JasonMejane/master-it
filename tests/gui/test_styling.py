from collections.abc import Callable

import pytest
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton
from pytestqt.qtbot import QtBot

from masterit.gui.styling import (
    BUTTON_ICON_SIZE,
    make_button,
    make_card,
    make_primary_button,
    make_section,
    mark_muted,
)

type ButtonMaker = Callable[[str, str], QPushButton]


def test_section_frames_a_titled_widget(qtbot: QtBot):
    content = QLineEdit()
    section = make_section("Links", content)
    qtbot.addWidget(section)
    title = section.findChild(QLabel, "sectionTitle")
    assert section.objectName() == "section"
    assert title is not None
    assert title.text() == "Links"
    assert content.parent() is section


def test_card_frames_content_without_title(qtbot: QtBot):
    content = QLineEdit()
    card = make_card(content)
    qtbot.addWidget(card)
    assert card.objectName() == "section"
    assert card.findChild(QLabel, "sectionTitle") is None
    assert content.parent() is card


def test_section_accepts_a_layout(qtbot: QtBot):
    row = QHBoxLayout()
    content = QLineEdit()
    row.addWidget(content)
    section = make_section("Output", row)
    qtbot.addWidget(section)
    assert content.parent() is section


def test_button_has_an_icon_and_no_role(qtbot: QtBot):
    button = make_button("Browse…", "folder-open")
    qtbot.addWidget(button)
    assert button.text() == "Browse…"
    assert not button.icon().isNull()
    assert button.property("role") is None


def test_primary_button_is_marked_for_the_accent_style(qtbot: QtBot):
    button = make_primary_button("Download", "download")
    qtbot.addWidget(button)
    assert button.property("role") == "primary"
    assert not button.icon().isNull()


@pytest.mark.parametrize("make", [make_button, make_primary_button])
def test_buttons_leave_a_gap_between_icon_and_text(qtbot: QtBot, make: ButtonMaker):
    button = make("Browse…", "folder-open")
    qtbot.addWidget(button)
    assert button.iconSize() == BUTTON_ICON_SIZE
    assert BUTTON_ICON_SIZE.width() > BUTTON_ICON_SIZE.height()


def test_muted_label_is_marked(qtbot: QtBot):
    label = QLabel()
    qtbot.addWidget(label)
    mark_muted(label)
    assert label.property("muted") is True


def test_section_title_is_tied_to_its_widget(qtbot: QtBot):
    content = QLineEdit()
    section = make_section("Links", content)
    qtbot.addWidget(section)
    title = section.findChild(QLabel, "sectionTitle")
    assert title is not None
    assert title.buddy() is content
