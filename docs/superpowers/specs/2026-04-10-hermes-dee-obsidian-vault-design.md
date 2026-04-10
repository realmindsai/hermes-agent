# Hermes Dee Obsidian Vault Mount Design

## Goal

Mount Dee's Obsidian git repo into the Totoro Docker deployment for `hermes-dee` only, with read-write access, while avoiding root-owned file writes into the host repo.

## Current State

- Totoro runs Hermes through Docker Compose and systemd.
- `hermes-dee` and `hermes-tracy` both use `hermes-gateway:latest`.
- The checked-in Dee config sets `terminal.cwd: "/workspace"`.
- The checked-in Compose file does not mount anything at `/workspace`.
- The live `hermes-dee` container currently runs as `root`.
- Dee's Obsidian vault on Totoro is the git repo at `/tank/personal/obsidian-personal`.

## Problem

If Hermes gets a direct read-write bind mount to the Obsidian vault while still running as `root`, it can create root-owned files in the host repo. That is an avoidable foot-gun. The current `/workspace` cwd is also misleading because no such mount exists in the container.

## Requirements

### Functional

- `hermes-dee` must have a writable bind mount to `/tank/personal/obsidian-personal`.
- The mount must not be added to `hermes-tracy`.
- Dee's terminal and file tools must start in the mounted vault path.
- The mounted path should mirror the Nanoclaw-style namespace: `/workspace/extra/obsidian`.

### Safety

- Writes into the vault must land as host user `dewoller`, not `root`.
- Existing Dee instance state in `/data` must remain writable.
- The mounted secrets file `/data/.env` must remain readable to the container user.

### Documentation

- The Totoro deployment note must describe the Obsidian mount and the container user choice.
- The old caveat about `/workspace` not being mounted must be replaced with the new actual layout.

## Chosen Approach

Update the Dee service only:

1. Add a writable bind mount from `/tank/personal/obsidian-personal` to `/workspace/extra/obsidian`.
2. Run `hermes-dee` as `1000:1004`.
3. Change Dee's `terminal.cwd` to `/workspace/extra/obsidian`.

Why `1000:1004`:

- `1000` is the host uid for `dewoller`, which owns the Obsidian vault.
- `1004` is the group that owns Dee's `HERMES_HOME` and the mounted `.env` file.
- This lets the container write the vault as `dewoller` and still access Dee's state and secrets.

## Files Affected

- `deploy/docker-compose.yaml`
- `deploy/config-dee.yaml`
- `deploy/totoro_docker_install.md`
- `tests/hermes_cli/test_totoro_deploy_config.py`
- `tests/integration/test_totoro_obsidian_mount_contract.py`
- `tests/e2e/test_totoro_obsidian_mount_contract.py`

## Test Strategy

### Unit

Parse the checked-in deployment YAML and assert:

- `hermes-dee` has `user: "1000:1004"`
- `hermes-dee` mounts the Obsidian repo at `/workspace/extra/obsidian`
- `hermes-tracy` does not
- Dee config uses `terminal.cwd: "/workspace/extra/obsidian"`

### Integration

Assert the cross-file deployment contract:

- Dee compose mount destination matches Dee config cwd root
- the host path is the Totoro Obsidian repo path
- only Dee gets the vault mount

### E2E

Treat the shipped deployment artifacts as the end-to-end contract and assert:

- the compose artifact, Dee config, and deployment doc all describe the same Obsidian mount
- the docs mention Dee-only scope and the non-root container user

## Non-Goals

- No Tracy vault mount
- No generic mount configuration system
- No changes to Hermes tool permission logic
- No automatic git pull/commit/push workflow for the vault

## Acceptance Criteria

- Restarting `hermes-dee` on Totoro results in a container that sees `/workspace/extra/obsidian`.
- Files created from inside the Dee container in the mounted vault are owned by `dewoller`, not `root`.
- `hermes-tracy` remains unchanged.
- Tests covering the static deployment contract pass.
