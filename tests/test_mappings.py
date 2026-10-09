"""Tests for the pure value-mapping helpers."""

from __future__ import annotations

import pytest

from custom_components.fp_smart_connect.mappings import (
    SETTLING_PLAYLIST_MAP,
    EnumMapping,
    PlaylistMapping,
    UnknownTracksError,
    normalize_option,
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


def test_enum_mapping_known_and_fallback_options() -> None:
    """Known values map to their options; unknown values get a generic fallback."""
    mapping = EnumMapping({"slow": 0, "fast": 1}, fallback_prefix="speed")

    assert mapping.option_for(0) == "slow"
    assert mapping.option_for(1) == "fast"
    assert mapping.option_for(9) == "speed_9"
    assert mapping.raw_for("slow") == 0
    assert mapping.raw_for("speed_9") == 9
    assert mapping.raw_for("speed_nine") is None
    assert mapping.raw_for("Slow") is None
    assert mapping.raw_for("nonsense") is None


def test_enum_mapping_options_for_includes_fallback_only_when_needed() -> None:
    """options_for() keeps current_option a member of options without inflating the list."""
    mapping = EnumMapping({"slow": 0, "fast": 1}, fallback_prefix="speed")

    assert mapping.options_for(0) == ["slow", "fast"]
    assert mapping.options_for(9) == ["slow", "fast", "speed_9"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("very_fast", "very_fast"),
        ("Very Fast", "very_fast"),
        ("10 Minutes", "10_minutes"),
        ("Brahms: Lullaby", "brahms_lullaby"),
        ("It's Raining, It's Pouring", "its_raining_its_pouring"),
        ("It\u2019s Raining", "its_raining"),
        ("  Off  ", "off"),
    ],
)
def test_normalize_option(value: str, expected: str) -> None:
    """Display names normalize to option form, and options pass through."""
    assert normalize_option(value) == expected


@pytest.mark.parametrize("native_max", [7, 15])
def test_brightness_round_trips_every_native_level(native_max: int) -> None:
    """Every native level survives a trip through Home Assistant's 0-255 scale."""
    for level in range(native_max + 1):
        assert (
            scale_from_ha_brightness(
                scale_to_ha_brightness(level, native_max), native_max
            )
            == level
        )


def test_volume_round_trips_every_native_level() -> None:
    """Every native volume level survives a trip through Home Assistant's 0.0-1.0."""
    for level in range(16):
        assert volume_from_ha(volume_to_ha(level)) == level


def test_out_of_range_values_are_clamped() -> None:
    """Out-of-range inputs clamp to the valid range instead of overflowing."""
    assert scale_to_ha_brightness(-1, 7) == 0
    assert scale_to_ha_brightness(99, 7) == 255
    assert scale_from_ha_brightness(-5, 7) == 0
    assert scale_from_ha_brightness(300, 7) == 7
    assert volume_to_ha(-1) == pytest.approx(0.0)
    assert volume_to_ha(20) == pytest.approx(1.0)
    assert volume_from_ha(-0.1) == 0
    assert volume_from_ha(1.5) == 15


def test_enum_mapping_with_off() -> None:
    """with_off() adds an "off" option for 0 without touching the original."""
    mapping = EnumMapping({"on": 1}, fallback_prefix="mode")

    with_off = mapping.with_off()

    assert with_off.option_to_raw == {"off": 0, "on": 1}
    assert with_off.option_for(0) == "off"
    assert mapping.option_for(0) == "mode_0"


PLAYLIST = PlaylistMapping.from_source(
    {"first": 1, "second": 2, "third": 4}, overrides={"third": "Third!"}
)


@pytest.mark.parametrize(
    ("mask", "expected"),
    [
        (0, []),
        (0b001, ["First"]),
        (0b101, ["First", "Third!"]),
        (0b111, ["First", "Second", "Third!"]),
        (0b1010, ["Second", "Track 4"]),
    ],
)
def test_playlist_labels_for(mask: int, expected: list[str]) -> None:
    """Set bits map to track labels in bit order; unknown bits get a fallback."""
    assert PLAYLIST.labels_for(mask) == expected


@pytest.mark.parametrize(
    ("track", "expected"),
    [
        ("First", 1),
        ("third!", 4),
        ("  SECOND ", 2),
        ("third", 4),
        (1, 1),
        (3, 4),
        ("2", 2),
        (0, None),
        (4, None),
        ("Track 4", None),
        ("nonsense", None),
    ],
)
def test_playlist_bit_for(track: str | int, expected: int | None) -> None:
    """Tracks resolve by case-insensitive name or 1-based index."""
    assert PLAYLIST.bit_for(track) == expected


def test_playlist_mask_for() -> None:
    """Names and indexes combine into one mask; duplicates are harmless."""
    assert PLAYLIST.mask_for(["First", 3, "first"]) == 0b101


def test_playlist_mask_for_rejects_every_unknown_track() -> None:
    """Every unknown track is reported, and nothing is partially resolved."""
    with pytest.raises(UnknownTracksError) as exc_info:
        PLAYLIST.mask_for(["First", "Nope", 9])

    assert exc_info.value.tracks == ["Nope", "9"]


def test_settling_playlist_labels_match_sound_labels() -> None:
    """Settling track names share the sound source's punctuation overrides."""
    assert SETTLING_PLAYLIST_MAP.labels_for(0b10001) == [
        "It's Raining, It's Pouring",
        "Brahms: Lullaby",
    ]
