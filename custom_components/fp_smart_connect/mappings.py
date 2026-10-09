"""
Value-mapping helpers between fp_soother_lib and Home Assistant's entity models.

Pure logic only -- no homeassistant imports -- so it can be exercised directly
in unit tests without any Home Assistant test scaffolding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from fp_soother_lib.constants import (
    ANIMAL_PROJECTION_MODES,
    ANIMAL_PROJECTION_SPEEDS,
    CAPTIVE_PLAYLIST_TRACKS,
    CUSTOM_COLORS,
    SLEEP_STAGE_TIMER_DURATIONS,
    SLEEP_STAGES_MODES,
    SLEEP_TIMER_DURATIONS,
    SOOTHE_PLAYLIST_TRACKS,
    SOUND_MODES,
    STAR_PROJECTION_SEQUENCES,
    STAR_PROJECTION_SPEEDS,
    TIMER_DURATIONS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

NIGHTLIGHT_BRIGHTNESS_MAX = 7
STAR_PROJECTION_BRIGHTNESS_MAX = 6
ANIMAL_PROJECTION_BRIGHTNESS_MAX = 10
VOLUME_MAX = 15
HA_BRIGHTNESS_MAX = 255


def scale_to_ha_brightness(value: int, native_max: int) -> int:
    """Scale a native 0..native_max value to Home Assistant's 0..255 brightness."""
    value = max(0, min(value, native_max))
    return round(value * HA_BRIGHTNESS_MAX / native_max)


def scale_from_ha_brightness(brightness: int, native_max: int) -> int:
    """Scale a Home Assistant 0..255 brightness value to a native 0..native_max."""
    brightness = max(0, min(brightness, HA_BRIGHTNESS_MAX))
    return round(brightness * native_max / HA_BRIGHTNESS_MAX)


def volume_to_ha(level: int) -> float:
    """Scale a native 0..15 volume level to Home Assistant's 0.0..1.0 volume_level."""
    return max(0, min(level, VOLUME_MAX)) / VOLUME_MAX


def volume_from_ha(volume: float) -> int:
    """Scale a Home Assistant 0.0..1.0 volume_level to a native 0..15 volume level."""
    return round(max(0.0, min(volume, 1.0)) * VOLUME_MAX)


def normalize_option(value: str) -> str:
    """
    Normalize an option or its English display name to option form.

    Lowercases, drops apostrophes, and collapses every other run of
    non-alphanumeric characters to "_", so "Very Fast" -> "very_fast" and
    "It's Raining, It's Pouring" -> "its_raining_its_pouring". Options pass
    through unchanged.
    """
    folded = value.casefold().replace("'", "").replace("\u2019", "")
    return re.sub(r"[^a-z0-9]+", "_", folded).strip("_")


def _title_case(key: str) -> str:
    """Title-case a snake_case constants key, e.g. "very_fast" -> "Very Fast"."""
    return " ".join(word.capitalize() for word in key.split("_"))


@dataclass(frozen=True)
class EnumMapping:
    """
    An option<->raw-int mapping backed by one of fp_soother_lib.constants's dicts.

    Options are the library's own snake_case keys (e.g. "very_fast"), used
    as-is as entity states and action values; Home Assistant shows their
    display names from strings.json. Unknown raw values are never dropped:
    option_for() returns a generic "{fallback_prefix}_{raw}" option instead,
    and options_for() includes that fallback so a SelectEntity's
    current_option always stays a member of its own options list.
    """

    option_to_raw: dict[str, int]
    fallback_prefix: str
    raw_to_option: dict[int, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Precompute the reverse lookup."""
        object.__setattr__(
            self,
            "raw_to_option",
            {raw: option for option, raw in self.option_to_raw.items()},
        )

    def option_for(self, raw: int) -> str:
        """Return the known option for raw, or a generic fallback option."""
        if raw in self.raw_to_option:
            return self.raw_to_option[raw]
        return f"{self.fallback_prefix}_{raw}"

    def raw_for(self, option: str) -> int | None:
        """Return the raw value for a known or fallback option, or None."""
        if option in self.option_to_raw:
            return self.option_to_raw[option]
        prefix = f"{self.fallback_prefix}_"
        if (
            option.startswith(prefix)
            and (suffix := option.removeprefix(prefix)).isdigit()
        ):
            return int(suffix)
        return None

    def options_for(self, current_raw: int) -> list[str]:
        """Return the known options, plus a fallback if current_raw is unknown."""
        options = list(self.option_to_raw)
        if current_raw not in self.raw_to_option:
            options.append(self.option_for(current_raw))
        return options

    def with_off(self) -> EnumMapping:
        """Return a copy that also maps "off" to 0, for modes where 0 is off."""
        return EnumMapping(
            option_to_raw={OFF_OPTION: 0, **self.option_to_raw},
            fallback_prefix=self.fallback_prefix,
        )


class UnknownTracksError(ValueError):
    """Raised when one or more requested playlist tracks are not recognized."""

    def __init__(self, tracks: list[str]) -> None:
        """Initialize with the unrecognized tracks, as given."""
        super().__init__(f"Unknown tracks: {', '.join(tracks)}")
        self.tracks = tracks


@dataclass(frozen=True)
class PlaylistMapping:
    """
    A track-name<->bit mapping for one of the device's playlist bitmasks.

    A track is addressed by its name, matched via normalize_option(), or by
    its 1-based track index, which selects
    bit (index - 1) of the mask. Unknown set bits are never dropped:
    labels_for() renders them as a generic "Track <index>" label.
    """

    label_to_bit: dict[str, int]
    bit_to_label: dict[int, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Precompute the reverse lookup."""
        object.__setattr__(
            self,
            "bit_to_label",
            {bit: label for label, bit in self.label_to_bit.items()},
        )

    @classmethod
    def from_source(
        cls, source: dict[str, int], *, overrides: dict[str, str] | None = None
    ) -> PlaylistMapping:
        """Build a mapping from one of fp_soother_lib.constants's track dicts."""
        overrides = overrides or {}
        return cls(
            label_to_bit={
                overrides.get(key, _title_case(key)): bit for key, bit in source.items()
            }
        )

    def labels_for(self, mask: int) -> list[str]:
        """Return the labels of every track selected in mask, in bit order."""
        labels = []
        index = 1
        while mask >= (bit := 1 << (index - 1)):
            if mask & bit:
                labels.append(self.bit_to_label.get(bit, f"Track {index}"))
            index += 1
        return labels

    def bit_for(self, track: str | int) -> int | None:
        """
        Return the mask bit for a track name or 1-based index, or None.

        Names are compared via normalize_option(), so a track matches its
        display name in any case or its library key ("Brahms: Lullaby",
        "brahms lullaby", and "brahms_lullaby" are the same track).
        """
        if isinstance(track, str):
            if not track.strip().isdigit():
                normalized = normalize_option(track)
                return next(
                    (
                        bit
                        for label, bit in self.label_to_bit.items()
                        if normalize_option(label) == normalized
                    ),
                    None,
                )
            track = int(track)
        if track < 1:
            return None
        bit = 1 << (track - 1)
        return bit if bit in self.bit_to_label else None

    def mask_for(self, tracks: Iterable[str | int]) -> int:
        """
        Resolve track names and/or indexes to a bitmask.

        Raises UnknownTracksError listing every unrecognized track, so nothing
        is partially applied.
        """
        mask = 0
        unknown: list[str] = []
        for track in tracks:
            bit = self.bit_for(track)
            if bit is None:
                unknown.append(str(track))
            else:
                mask |= bit
        if unknown:
            raise UnknownTracksError(unknown)
        return mask


OFF_OPTION = "off"
NO_TRACKS_LABEL = "No tracks"

# Track names that plain title-casing of the constants key can't reproduce.
TRACK_LABEL_OVERRIDES = {
    "its_raining_its_pouring": "It's Raining, It's Pouring",
    "brahms_lullaby": "Brahms: Lullaby",
}

SOUND_MODE_MAP = EnumMapping(dict(SOUND_MODES), fallback_prefix="mode")
STAR_PROJECTION_EFFECT_MAP = EnumMapping(
    dict(STAR_PROJECTION_SEQUENCES), fallback_prefix="sequence"
)
ANIMAL_PROJECTION_EFFECT_MAP = EnumMapping(
    dict(ANIMAL_PROJECTION_MODES), fallback_prefix="mode"
)
STAR_PROJECTION_SPEED_MAP = EnumMapping(
    dict(STAR_PROJECTION_SPEEDS), fallback_prefix="speed"
)
ANIMAL_PROJECTION_SPEED_MAP = EnumMapping(
    dict(ANIMAL_PROJECTION_SPEEDS), fallback_prefix="speed"
)
TIMER_DURATION_MAP = EnumMapping(dict(TIMER_DURATIONS), fallback_prefix="setting")
SLEEP_STAGES_MODE_MAP = EnumMapping(dict(SLEEP_STAGES_MODES), fallback_prefix="mode")
SLEEP_STAGE_TIMER_MAP = EnumMapping(
    dict(SLEEP_STAGE_TIMER_DURATIONS), fallback_prefix="setting"
)
SLEEP_TIMER_MAP = EnumMapping(dict(SLEEP_TIMER_DURATIONS), fallback_prefix="setting")
CUSTOM_COLOR_MAP = EnumMapping(dict(CUSTOM_COLORS), fallback_prefix="color")

SETTLING_PLAYLIST_MAP = PlaylistMapping.from_source(
    CAPTIVE_PLAYLIST_TRACKS, overrides=TRACK_LABEL_OVERRIDES
)
SOOTHING_PLAYLIST_MAP = PlaylistMapping.from_source(SOOTHE_PLAYLIST_TRACKS)
