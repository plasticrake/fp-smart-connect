"""Tests that icons.json covers every entity and action."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from custom_components.fp_smart_connect import const
from custom_components.fp_smart_connect.light import (
    LIGHT_DESCRIPTIONS,
    FpSootherLightDescription,
)
from custom_components.fp_smart_connect.select import (
    SELECT_DESCRIPTIONS,
    FpSootherSelectDescription,
)

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


def _icon_sections() -> list[dict[str, Any]]:
    """Return every entity icon section, including state attribute sections."""
    sections = []
    for entries in ICONS["entity"].values():
        for entry in entries.values():
            sections.append(entry)
            sections.extend(entry.get("state_attributes", {}).values())
    return sections


def test_every_icon_section_has_a_default() -> None:
    """Every entity and state attribute icon section declares a default icon."""
    for section in _icon_sections():
        assert "default" in section


def test_icons_are_mdi() -> None:
    """Every icon value names a Material Design Icon (starts with "mdi:")."""
    entity_icons = [
        icon
        for section in _icon_sections()
        for icon in [section["default"], *section.get("state", {}).values()]
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
    for section in _icon_sections():
        for state, icon in section.get("state", {}).items():
            assert re.fullmatch(r"[a-z0-9_-]+", state)
            assert icon != section.get("default")


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
def test_select_state_icons_name_real_options(
    description: FpSootherSelectDescription,
) -> None:
    """Select state icons are keyed by options the select actually offers."""
    states = ICONS["entity"]["select"][description.translation_key].get("state", {})
    assert set(states) <= set(description.value_map.option_to_raw)


@pytest.mark.parametrize(
    "description",
    [d for d in LIGHT_DESCRIPTIONS if d.effect_map is not None],
    ids=lambda d: d.key,
)
def test_effect_icons_name_real_effects(
    description: FpSootherLightDescription,
) -> None:
    """Light effect icons are keyed by effects the light actually offers."""
    assert description.effect_map is not None
    entry = ICONS["entity"]["light"][description.translation_key]
    states = entry["state_attributes"]["effect"]["state"]
    assert set(states) <= set(description.effect_map.option_to_raw)
