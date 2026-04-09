#!/bin/bash
# Gateway container entrypoint: bootstrap HERMES_HOME, then run hermes gateway.
set -e

HERMES_HOME="${HERMES_HOME:-/data}"
INSTALL_DIR="/opt/hermes"

# Create essential directory structure
mkdir -p "$HERMES_HOME"/{cron,sessions,logs,hooks,memories,skills,cache}

# Bootstrap config.yaml if missing (but prefer bind-mounted one)
if [ ! -f "$HERMES_HOME/config.yaml" ] && [ ! -L "$HERMES_HOME/config.yaml" ]; then
    cp "$INSTALL_DIR/cli-config.yaml.example" "$HERMES_HOME/config.yaml"
    echo "Bootstrapped default config.yaml"
fi

# Bootstrap SOUL.md if missing
if [ ! -f "$HERMES_HOME/SOUL.md" ]; then
    cp "$INSTALL_DIR/docker/SOUL.md" "$HERMES_HOME/SOUL.md"
fi

# Sync bundled skills
if [ -d "$INSTALL_DIR/skills" ]; then
    python3 "$INSTALL_DIR/tools/skills_sync.py" 2>/dev/null || true
fi

exec hermes "$@"
