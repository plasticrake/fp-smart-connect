"""
Value-mapping helpers between fp_soother_lib and Home Assistant's entity models.

Pure logic only -- no homeassistant imports -- so it can be exercised directly
in unit tests without any Home Assistant test scaffolding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fp_soother_lib.constants import (
    ANIMAL_PROJECTION_MODES,
    ANIMAL_PROJECTION_SPEEDS,
    CUSTOM_COLORS,
    SLEEP_STAGE_TIMER_DURATIONS,
    SLEEP_STAGES_MODES,
    SLEEP_TIMER_DURATIONS,
    SOUND_MODES,
    STAR_PROJECTION_SEQUENCES,
    STAR_PROJECTION_SPEEDS,
    TIMER_DURATIONS,
)

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


# Display labels that plain title-casing of the constants key can't reproduce.
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
