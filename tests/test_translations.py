"""Tests that every enum option has a display name, and en.json tracks strings.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fp_soother_lib.constants import SOUND_MODES

from custom_components.fp_smart_connect import const
from custom_components.fp_smart_connect.light import LIGHT_DESCRIPTIONS
from custom_components.fp_smart_connect.mappings import (
    SETTLING_PLAYLIST_MAP,
    SOOTHING_PLAYLIST_MAP,
    SOUND_MODE_MAP,
    normalize_option,
)
from custom_components.fp_smart_connect.select import SELECT_DESCRIPTIONS

COMPONENT_DIR = Path(const.__file__).parent
STRINGS = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
EN = json.loads(
    (COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8")
)
SERVICES = yaml.safe_load((COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8"))
ENTITY = STRINGS["entity"]


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
def test_select_options_are_translated(description) -> None:
    """Each select option has a display name under its translation key."""
    states = ENTITY["select"][description.translation_key]["state"]
    assert set(states) == set(description.value_map.option_to_raw)


@pytest.mark.parametrize(
    "description",
    [d for d in LIGHT_DESCRIPTIONS if d.effect_map is not None],
    ids=lambda d: d.key,
)
def test_light_effects_are_translated(description) -> None:
    """Each light effect has a display name under its translation key."""
    assert description.effect_map is not None
    attrs = ENTITY["light"][description.translation_key]["state_attributes"]
    assert set(attrs["effect"]["state"]) == set(description.effect_map.option_to_raw)


def test_sound_sources_are_translated() -> None:
    """Each sound source has a display name."""
    attrs = ENTITY["media_player"]["sound"]["state_attributes"]
    assert set(attrs["source"]["state"]) == set(SOUND_MODE_MAP.option_to_raw)


def test_sound_names_match_playlist_track_names() -> None:
    """A track's sound source display name matches its playlist track name."""
    names = ENTITY["media_player"]["sound"]["state_attributes"]["source"]["state"]
    for playlist in (SETTLING_PLAYLIST_MAP, SOOTHING_PLAYLIST_MAP):
        for track in playlist.label_to_bit:
            matches = [key for key, name in names.items() if name == track]
            assert len(matches) == 1, track
            assert matches[0] in SOUND_MODES


@pytest.mark.parametrize(
    ("service", "field"),
    [
        (service, field)
        for service, spec in SERVICES.items()
        for field, field_spec in spec["fields"].items()
        if "translation_key" in field_spec["selector"].get("select", {})
    ],
)
def test_action_select_options_are_translated(service: str, field: str) -> None:
    """Each translated action select option has a display name."""
    select = SERVICES[service]["fields"][field]["selector"]["select"]
    names = STRINGS["selector"][select["translation_key"]]["options"]
    assert set(names) == set(select["options"])


def test_every_enum_preset_field_is_translated() -> None:
    """apply_preset select fields all use translated options, except track lists."""
    untranslated = {
        field
        for field, spec in SERVICES["apply_preset"]["fields"].items()
        if "select" in spec["selector"]
        and "translation_key" not in spec["selector"]["select"]
    }
    assert untranslated == {"captive_playlist_selection", "soothe_playlist_selection"}


def _display_names(section: Any) -> list[tuple[str, str]]:
    """Return every (option, display name) pair under a state/options section."""
    pairs = []
    if isinstance(section, dict):
        for key, value in section.items():
            if key in {"state", "options"} and isinstance(value, dict):
                pairs.extend(value.items())
            else:
                pairs.extend(_display_names(value))
    return pairs


def test_display_names_normalize_to_their_options() -> None:
    """apply_preset can accept display names because each one maps back to its option."""
    pairs = _display_names({"entity": EN["entity"], "selector": EN["selector"]})
    assert pairs
    for option, name in pairs:
        assert normalize_option(name) == option, name


def _compare(strings: Any, en: Any, path: str) -> None:
    if isinstance(strings, dict):
        assert isinstance(en, dict), path
        assert set(strings) == set(en), path
        for key, value in strings.items():
            _compare(value, en[key], f"{path}.{key}")
    elif not (isinstance(strings, str) and strings.startswith("[%key:")):
        assert strings == en, path


def test_en_json_matches_strings_json() -> None:
    """en.json is strings.json with only the [%key:...] references resolved."""
    _compare(STRINGS, EN, "")
