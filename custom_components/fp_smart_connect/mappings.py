"""
Value-mapping helpers between fp_soother_lib and Home Assistant's entity models.

Pure logic only -- no homeassistant imports -- so it can be exercised directly
in unit tests without any Home Assistant test scaffolding.
"""

from __future__ import annotations

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
STAR_PROJECTION_BRIGHTNESS_MAX = 7
ANIMAL_PROJECTION_BRIGHTNESS_MAX = 15
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


def _title_case(key: str) -> str:
    """Title-case a snake_case constants key, e.g. "very_fast" -> "Very Fast"."""
    return " ".join(word.capitalize() for word in key.split("_"))


@dataclass(frozen=True)
class EnumMapping:
    """
    A label<->raw-int mapping backed by one of fp_soother_lib.constants's dicts.

    Unknown raw values are never dropped: label_for() returns a generic
    "{fallback_prefix} {raw}" label instead, and options_for() includes that
    fallback label so a SelectEntity's current_option always stays a member
    of its own options list.
    """

    label_to_raw: dict[str, int]
    fallback_prefix: str
    raw_to_label: dict[int, str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Precompute the reverse lookup."""
        object.__setattr__(
            self,
            "raw_to_label",
            {raw: label for label, raw in self.label_to_raw.items()},
        )

    @classmethod
    def from_source(
        cls,
        source: dict[str, int],
        *,
        fallback_prefix: str,
        overrides: dict[str, str] | None = None,
    ) -> EnumMapping:
        """
        Build a mapping from one of fp_soother_lib.constants's label->int dicts.

        `overrides` supplies display labels that plain title-casing of the
        snake_case source key can't reproduce (e.g. contractions, punctuation).
        """
        overrides = overrides or {}
        label_to_raw = {
            overrides.get(key, _title_case(key)): raw for key, raw in source.items()
        }
        return cls(label_to_raw=label_to_raw, fallback_prefix=fallback_prefix)

    def label_for(self, raw: int) -> str:
        """Return the known label for raw, or a generic fallback label."""
        if raw in self.raw_to_label:
            return self.raw_to_label[raw]
        return f"{self.fallback_prefix} {raw}"

    def raw_for(self, label: str) -> int | None:
        """Return the raw value for a known label, or None."""
        if label in self.label_to_raw:
            return self.label_to_raw[label]
        prefix = f"{self.fallback_prefix} "
        if (
            label.startswith(prefix)
            and (suffix := label.removeprefix(prefix)).isdigit()
        ):
            return int(suffix)
        return None

    def options_for(self, current_raw: int) -> list[str]:
        """Return the known labels, plus a fallback if current_raw is unknown."""
        options = list(self.label_to_raw)
        if current_raw not in self.raw_to_label:
            options.append(self.label_for(current_raw))
        return options


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

    A track can also be addressed by its 1-based track index, which selects
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
        """Return the mask bit for a track name or 1-based index, or None."""
        if isinstance(track, str):
            if not track.strip().isdigit():
                folded = track.strip().casefold()
                return next(
                    (
                        bit
                        for label, bit in self.label_to_bit.items()
                        if label.casefold() == folded
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


NO_TRACKS_LABEL = "No tracks"

# Display labels that plain title-casing of the constants key can't reproduce.
# Shared by the sound modes and the settling playlist's track names.
TRACK_LABEL_OVERRIDES = {
    "its_raining_its_pouring": "It's Raining, It's Pouring",
    "brahms_lullaby": "Brahms: Lullaby",
}

SOUND_MODE_MAP = EnumMapping.from_source(
    SOUND_MODES, fallback_prefix="Mode", overrides=TRACK_LABEL_OVERRIDES
)
STAR_PROJECTION_EFFECT_MAP = EnumMapping.from_source(
    STAR_PROJECTION_SEQUENCES, fallback_prefix="Sequence"
)
ANIMAL_PROJECTION_EFFECT_MAP = EnumMapping.from_source(
    ANIMAL_PROJECTION_MODES, fallback_prefix="Mode"
)
STAR_PROJECTION_SPEED_MAP = EnumMapping.from_source(
    STAR_PROJECTION_SPEEDS, fallback_prefix="Speed"
)
ANIMAL_PROJECTION_SPEED_MAP = EnumMapping.from_source(
    ANIMAL_PROJECTION_SPEEDS, fallback_prefix="Speed"
)
TIMER_DURATION_MAP = EnumMapping.from_source(TIMER_DURATIONS, fallback_prefix="Setting")
SLEEP_STAGES_MODE_MAP = EnumMapping.from_source(
    SLEEP_STAGES_MODES, fallback_prefix="Mode"
)
SLEEP_STAGE_TIMER_MAP = EnumMapping.from_source(
    SLEEP_STAGE_TIMER_DURATIONS, fallback_prefix="Setting"
)
SLEEP_TIMER_MAP = EnumMapping.from_source(
    SLEEP_TIMER_DURATIONS, fallback_prefix="Setting"
)
CUSTOM_COLOR_MAP = EnumMapping.from_source(CUSTOM_COLORS, fallback_prefix="Color")

SETTLING_PLAYLIST_MAP = PlaylistMapping.from_source(
    CAPTIVE_PLAYLIST_TRACKS, overrides=TRACK_LABEL_OVERRIDES
)
SOOTHING_PLAYLIST_MAP = PlaylistMapping.from_source(SOOTHE_PLAYLIST_TRACKS)
