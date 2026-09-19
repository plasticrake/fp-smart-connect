"""Tests for the pure value-mapping helpers."""

from __future__ import annotations

import pytest

from custom_components.fp_smart_connect.mappings import (
    EnumMapping,
    scale_from_ha_brightness,
    scale_to_ha_brightness,
    volume_from_ha,
    volume_to_ha,
)


@pytest.mark.parametrize(
    ("value", "native_max", "expected"),
    [(0, 7, 0), (7, 7, 255), (0, 15, 0), (15, 15, 255), (8, 15, 136)],
)
def test_scale_to_ha_brightness(value: int, native_max: int, expected: int) -> None:
    """Native values scale linearly to Home Assistant's 0-255 range."""
    assert scale_to_ha_brightness(value, native_max) == expected


@pytest.mark.parametrize(
    ("brightness", "native_max", "expected"),
    [(0, 7, 0), (255, 7, 7), (0, 15, 0), (255, 15, 15)],
)
def test_scale_from_ha_brightness(
    brightness: int, native_max: int, expected: int
) -> None:
    """Home Assistant brightness scales linearly back to the native range."""
    assert scale_from_ha_brightness(brightness, native_max) == expected


def test_volume_round_trip_boundaries() -> None:
    """Volume conversions are correct at both boundaries."""
    assert volume_to_ha(0) == pytest.approx(0.0)
    assert volume_to_ha(15) == pytest.approx(1.0)
    assert volume_from_ha(0.0) == 0
    assert volume_from_ha(1.0) == 15


def test_enum_mapping_known_and_fallback_labels() -> None:
    """Known values map to their labels; unknown values get a generic fallback."""
    mapping = EnumMapping.from_source({"slow": 0, "fast": 1}, fallback_prefix="Speed")

    assert mapping.label_for(0) == "Slow"
    assert mapping.label_for(1) == "Fast"
    assert mapping.label_for(9) == "Speed 9"
    assert mapping.raw_for("Slow") == 0
    assert mapping.raw_for("Speed 9") == 9
    assert mapping.raw_for("Speed nine") is None
    assert mapping.raw_for("nonsense") is None


def test_enum_mapping_overrides() -> None:
    """Overrides replace the auto-title-cased label for a given source key."""
    mapping = EnumMapping.from_source(
        {"its_raining": 1},
        fallback_prefix="Mode",
        overrides={"its_raining": "It's Raining"},
    )
    assert mapping.label_for(1) == "It's Raining"
    assert mapping.raw_for("It's Raining") == 1


def test_enum_mapping_options_for_includes_fallback_only_when_needed() -> None:
    """options_for() keeps current_option a member of options without inflating the list."""
    mapping = EnumMapping.from_source({"slow": 0, "fast": 1}, fallback_prefix="Speed")

    assert mapping.options_for(0) == ["Slow", "Fast"]
    assert mapping.options_for(9) == ["Slow", "Fast", "Speed 9"]
