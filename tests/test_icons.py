"""Tests that icons.json covers every entity and action."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from custom_components.fp_smart_connect import const

COMPONENT_DIR = Path(const.__file__).parent
ICONS = json.loads((COMPONENT_DIR / "icons.json").read_text(encoding="utf-8"))
STRINGS = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
SERVICES = yaml.safe_load((COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8"))


def _translation_keys(section: dict[str, dict[str, object]]) -> set[tuple[str, str]]:
    return {(platform, key) for platform, entries in section.items() for key in entries}


def test_every_entity_translation_key_has_an_icon() -> None:
    """Icons and entity strings declare the same platforms and translation keys."""
    assert _translation_keys(ICONS["entity"]) == _translation_keys(STRINGS["entity"])


def test_every_service_has_an_icon() -> None:
    """Each action in services.yaml has a service icon."""
    assert set(ICONS["services"]) == set(SERVICES)
    for icons in ICONS["services"].values():
        assert set(icons) == {"service"}


def test_icons_are_mdi() -> None:
    """Every icon value names a Material Design Icon."""
    entity_icons = [
        icon
        for entries in ICONS["entity"].values()
        for entry in entries.values()
        for icon in [entry["default"], *entry.get("state", {}).values()]
    ]
    service_icons = [entry["service"] for entry in ICONS["services"].values()]
    for icon in entity_icons + service_icons:
        assert icon.startswith("mdi:")


def test_state_icons_follow_hassfest_rules() -> None:
    """
    State icons are keyed by slug state values and differ from the default.

    Mirrors hassfest's icon schema, which rejects display-label keys such as
    "Very Fast" and state icons that repeat the default.
    """
    for entries in ICONS["entity"].values():
        for entry in entries.values():
            for state, icon in entry.get("state", {}).items():
                assert re.fullmatch(r"[a-z0-9_-]+", state)
                assert icon != entry["default"]
