# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project

A Home Assistant custom integration (HACS-distributable) for Fisher-Price Smart Connect devices, currently targeting only the Deluxe Soother (DYW47). All BLE protocol handling (encryption, packet construction, bit-field decoding, connection management) lives in the external `fp-soother-lib` package. This repo contains only the Home Assistant integration layer and must not duplicate that logic.

**Current state:** the `integration_blueprint` scaffold has been replaced with a real implementation: `coordinator.py`, `entity.py`, `light.py`, `media_player.py`, `select.py`, and `mappings.py` exist alongside `__init__.py` and `config_flow.py`, and `tests/` covers all of them. [DESIGN.md](DESIGN.md) remains the authoritative spec for the entity/action model. Read it before changing entity, action, or config-flow behavior, and keep it in sync when `fp-soother-lib`'s public API changes.

## Agent memory

Repository memory is not shared between AI agents. When verified project facts are added to repository memory, update this `AGENTS.md` with the reusable guidance so future agents receive it.

## Commands

- `scripts/setup` — `uv sync` the Python environment (also runs automatically as the devcontainer's `postCreateCommand`).
- `scripts/lint` — `uv run ruff format .` then `uv run ruff check . --fix`. Run this before considering any Python change done.
- `scripts/develop` — runs a local Home Assistant instance against `config/`, with `custom_components/` on `PYTHONPATH` so the integration loads without symlinks. First run bootstraps `config/` via `hass --script ensure_config`.
- `uv run pytest` — runs the test suite in `tests/` (config flow, coordinator, light, media player, select, and mappings). Run this before considering any Python change done, alongside `scripts/lint`.
- `uv run ty check` — type-checks the project. CI runs it alongside ruff and pytest, so it must pass too.

## Architecture notes

- **Domain**: `fp_smart_connect` (`custom_components/fp_smart_connect/const.py`). `manifest.json` already declares `integration_type: device`, `iot_class: local_push`, and `bluetooth_adapters` in `dependencies`, reflecting the push-notification-driven BLE model in DESIGN.md. Keep these in sync with the design if either changes.
- **Quality scale**: the integration targets bronze (custom integrations don't declare `quality_scale` in `manifest.json`), and `custom_components/fp_smart_connect/quality_scale.yaml` enumerates every Home Assistant Integration Quality Scale rule (bronze/silver/gold/platinum) with its status (`todo`, `done`, or `exempt`). Check this file against [Home Assistant's quality scale docs](https://developers.home-assistant.io/docs/core/integration-quality-scale/) when adding config-flow, entity, or discovery behavior, and flip rules to `done` as they're satisfied.
- **`fp-soother-lib` dependency**: installed from PyPI. It is declared in both `pyproject.toml` (`dependencies`, for the dev environment and tests) and `manifest.json` (`requirements`, which is what Home Assistant installs for users). Bump both together, re-run `uv lock`, and keep `loggers` in the manifest pointed at `fp_soother_lib`.
- **Linting**: `.ruff.toml` mirrors home-assistant/core's own ruff config, with `select = ["ALL"]` and a short, deliberate ignore list (formatter conflicts and `ANN401`). Don't add broad new ignores; fix the lint instead unless it genuinely conflicts with the formatter the way the existing entries do.
- **Python version**: `>=3.14.2` (`pyproject.toml`), ruff `target-version = "py314"`. This is newer than most Home Assistant core/integration code, so older-Python idioms and fallbacks are usually unnecessary.
- **Markdown prose**: rely on the editor's word-wrap. Write each paragraph or list item as a single line and don't hard-wrap prose at a fixed column.
