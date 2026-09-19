#!/usr/bin/env bash
set -euo pipefail

USER_NAME="$(id -un)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
GH_DIR="$HOME/.config/gh"

# Fix ownership only when the dir exists and isn't already ours. This makes the
# script idempotent: it skips the sudo call on rebuilds where the persisted
# volume is already correct.
for dir in "$GH_DIR" "$CLAUDE_DIR"; do
  if [ -d "$dir" ] && [ "$(stat -c '%U' "$dir")" != "$USER_NAME" ]; then
    sudo chown -R "$USER_NAME:$USER_NAME" "$dir"
  fi
done

# Seed an empty Claude config if missing so the extension's first locked save
# can lstat the file (avoids a noisy ENOENT error on a brand-new volume).
if [ ! -s "$CLAUDE_DIR/.claude.json" ]; then
  mkdir -p "$CLAUDE_DIR"
  echo '{}' > "$CLAUDE_DIR/.claude.json"
fi
