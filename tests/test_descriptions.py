"""
Guards against fp-soother-lib API drift.

SootherState is a plain (non-slotted) dataclass, so entity tests that
setattr() a renamed field would keep passing against a broken upgrade.
These check the entity descriptions against the real library instead.
"""

from __future__ import annotations

from dataclasses import fields
from unittest.mock import create_autospec

import pytest
from fp_soother_lib import SootherClient, SootherState
from fp_soother_lib.constants import (
    ANIMAL_PROJECTION_MODES,
    ANIMAL_PROJECTION_SPEEDS,
    SLEEP_STAGE_TIMER_DURATIONS,
    SLEEP_STAGES_MODES,
    SLEEP_TIMER_DURATIONS,
    SOUND_MODES,
    STAR_PROJECTION_SEQUENCES,
    STAR_PROJECTION_SPEEDS,
    TIMER_DURATIONS,
)

from custom_components.fp_smart_connect.light import (
    ANIMAL_PROJECTION,
    LIGHT_DESCRIPTIONS,
    STAR_PROJECTION,
    FpSootherLightDescription,
)
from custom_components.fp_smart_connect.mappings import EnumMapping
from custom_components.fp_smart_connect.media_player import SOUND_MODE_MAP
from custom_components.fp_smart_connect.select import (
    SELECT_DESCRIPTIONS,
    FpSootherSelectDescription,
)

STATE_FIELDS = {f.name for f in fields(SootherState)}

SELECT_SOURCES = {
    "star_projection_speed": STAR_PROJECTION_SPEEDS,
    "animal_projection_speed": ANIMAL_PROJECTION_SPEEDS,
    "music_timer": TIMER_DURATIONS,
    "light_timer": TIMER_DURATIONS,
    "sleep_stages": SLEEP_STAGES_MODES,
    "settle_timer": SLEEP_STAGE_TIMER_DURATIONS,
    "soothe_timer": SLEEP_STAGE_TIMER_DURATIONS,
    "sleep_timer": SLEEP_TIMER_DURATIONS,
}


@pytest.mark.parametrize("description", SELECT_DESCRIPTIONS, ids=lambda d: d.key)
def test_select_description_matches_library(
    description: FpSootherSelectDescription,
) -> None:
    """Each select reads a real SootherState field and calls a real client method."""
    assert description.state_attr in STATE_FIELDS
    assert callable(getattr(SootherClient, description.set_method, None))


@pytest.mark.parametrize("description", LIGHT_DESCRIPTIONS, ids=lambda d: d.key)
async def test_light_description_matches_library(
    description: FpSootherLightDescription,
) -> None:
    """Each light reads real SootherState fields and calls real client methods."""
    assert description.mode_attr in STATE_FIELDS
    assert description.brightness_attr in STATE_FIELDS
    if description.previous_mode_attr is not None:
        assert description.previous_mode_attr in STATE_FIELDS

    client = create_autospec(SootherClient, instance=True)
    await description.set_mode(client, 1)
    await description.set_brightness(client, 1)


@pytest.mark.parametrize(
    ("mapping", "source"),
    [
        pytest.param(SOUND_MODE_MAP, SOUND_MODES, id="sound"),
        pytest.param(
            STAR_PROJECTION.effect_map, STAR_PROJECTION_SEQUENCES, id="star_effects"
        ),
        pytest.param(
            ANIMAL_PROJECTION.effect_map, ANIMAL_PROJECTION_MODES, id="animal_effects"
        ),
        *(
            pytest.param(d.value_map, SELECT_SOURCES[d.key], id=d.key)
            for d in SELECT_DESCRIPTIONS
        ),
    ],
)
def test_mapping_is_lossless(
    mapping: EnumMapping | None, source: dict[str, int]
) -> None:
    """No two source entries collapse into one label or one raw value."""
    assert mapping is not None
    assert len(mapping.label_to_raw) == len(source)
    assert len(mapping.raw_to_label) == len(source)
    assert set(mapping.raw_to_label) == set(source.values())


def test_select_sources_cover_every_description() -> None:
    """SELECT_SOURCES stays in step with SELECT_DESCRIPTIONS."""
    assert set(SELECT_SOURCES) == {d.key for d in SELECT_DESCRIPTIONS}


@pytest.mark.parametrize(
    ("key", "label"),
    [
        ("its_raining_its_pouring", "It's Raining, It's Pouring"),
        ("brahms_lullaby", "Brahms: Lullaby"),
    ],
)
def test_sound_label_overrides_apply(key: str, label: str) -> None:
    """Overridden sound labels still match a real SOUND_MODES key."""
    assert key in SOUND_MODES
    assert SOUND_MODE_MAP.label_for(SOUND_MODES[key]) == label
