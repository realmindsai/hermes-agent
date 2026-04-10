# Hermes Dee Obsidian Vault Mount Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mount Dee's Obsidian git repo into the Totoro Docker deployment with read-write access while preventing root-owned writes into the host repo.

**Architecture:** The change is a deployment contract update, not a runtime feature. The Dee Docker service gains a writable Obsidian bind mount and runs as the host uid/gid needed to write the vault safely. Static tests enforce alignment between Docker Compose, Dee config, and the Totoro deployment note.

**Tech Stack:** Docker Compose YAML, Hermes deployment config YAML, pytest, PyYAML, Markdown docs

---

### Task 1: Add the failing deployment contract tests

**Files:**
- Create: `tests/hermes_cli/test_totoro_deploy_config.py`
- Create: `tests/integration/test_totoro_obsidian_mount_contract.py`
- Create: `tests/e2e/test_totoro_obsidian_mount_contract.py`
- Read: `deploy/docker-compose.yaml`
- Read: `deploy/config-dee.yaml`
- Read: `deploy/totoro_docker_install.md`

- [ ] **Step 1: Write the failing unit test**

```python
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: str):
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_hermes_dee_uses_non_root_obsidian_mount():
    compose = _load_yaml("deploy/docker-compose.yaml")
    dee = compose["services"]["hermes-dee"]
    tracy = compose["services"]["hermes-tracy"]

    assert dee["user"] == "1000:1004"
    assert "/tank/personal/obsidian-personal:/workspace/extra/obsidian" in dee["volumes"]
    assert all("/workspace/extra/obsidian" not in volume for volume in tracy["volumes"])


def test_hermes_dee_cwd_points_at_obsidian_mount():
    dee_config = _load_yaml("deploy/config-dee.yaml")
    assert dee_config["terminal"]["cwd"] == "/workspace/extra/obsidian"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/hermes_cli/test_totoro_deploy_config.py -q`
Expected: FAIL because `hermes-dee` does not yet define `user`, does not yet mount the Obsidian repo, and Dee config still points at `/workspace`.

- [ ] **Step 3: Write the failing integration test**

```python
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OBSIDIAN_HOST_PATH = "/tank/personal/obsidian-personal"
OBSIDIAN_CONTAINER_PATH = "/workspace/extra/obsidian"


def _load_yaml(path: str):
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_dee_obsidian_mount_contract_is_consistent():
    compose = _load_yaml("deploy/docker-compose.yaml")
    dee = compose["services"]["hermes-dee"]
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert f"{OBSIDIAN_HOST_PATH}:{OBSIDIAN_CONTAINER_PATH}" in dee["volumes"]
    assert dee["user"] == "1000:1004"
    assert dee_config["terminal"]["cwd"] == OBSIDIAN_CONTAINER_PATH
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_totoro_obsidian_mount_contract.py -q`
Expected: FAIL because the compose mount and Dee cwd contract is not yet implemented.

- [ ] **Step 5: Write the failing e2e artifact test**

```python
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_totoro_doc_describes_dee_obsidian_mount():
    doc = (REPO_ROOT / "deploy/totoro_docker_install.md").read_text(encoding="utf-8")
    assert "/tank/personal/obsidian-personal" in doc
    assert "/workspace/extra/obsidian" in doc
    assert "1000:1004" in doc
    assert "hermes-dee" in doc
    assert "hermes-tracy" in doc
```

- [ ] **Step 6: Run test to verify it fails**

Run: `python -m pytest tests/e2e/test_totoro_obsidian_mount_contract.py -q`
Expected: FAIL because the deployment doc does not yet describe the Obsidian mount or the non-root user choice.

### Task 2: Update Dee deployment artifacts

**Files:**
- Modify: `deploy/docker-compose.yaml`
- Modify: `deploy/config-dee.yaml`

- [ ] **Step 1: Add the Dee-only non-root user and Obsidian bind mount**

```yaml
services:
  hermes-dee:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.gateway
    image: hermes-gateway:latest
    container_name: hermes-dee
    user: "1000:1004"
    restart: "no"
    volumes:
      - /tank/services/active_services/hermes-dee:/data
      - /run/secrets/hermes-dee/.env:/data/.env:ro
      - /tank/services/active_services/hermes/deploy/config-dee.yaml:/opt/config-seed.yaml:ro
      - /tank/personal/obsidian-personal:/workspace/extra/obsidian
```

- [ ] **Step 2: Point Dee's terminal cwd at the mounted vault**

```yaml
terminal:
  backend: "local"
  cwd: "/workspace/extra/obsidian"
  timeout: 180
  lifetime_seconds: 300
```

- [ ] **Step 3: Run the unit and integration tests to verify the config passes**

Run: `python -m pytest tests/hermes_cli/test_totoro_deploy_config.py tests/integration/test_totoro_obsidian_mount_contract.py -q`
Expected: PASS

### Task 3: Update the Totoro deployment note

**Files:**
- Modify: `deploy/totoro_docker_install.md`

- [ ] **Step 1: Replace the old workspace caveat with the real Dee-only Obsidian mount**

```md
For `hermes-dee`, the compose file also mounts Dee's Obsidian vault:

- `/tank/personal/obsidian-personal` -> `/workspace/extra/obsidian`

`hermes-dee` runs as `1000:1004`, not `root`, so writes into the vault land as `dewoller` while Dee still keeps access to `/data` and the mounted `.env` file.

`hermes-tracy` does not get the Obsidian mount.
```

- [ ] **Step 2: Run the e2e artifact test to verify the doc and config agree**

Run: `python -m pytest tests/e2e/test_totoro_obsidian_mount_contract.py -q`
Expected: PASS

### Task 4: Verify the live Totoro deployment

**Files:**
- Read: `deploy/deploy.sh`

- [ ] **Step 1: Deploy the updated Dee service to Totoro**

Run: `./deploy/deploy.sh totoro_ts dee`
Expected: script pulls latest code on Totoro, rebuilds `hermes-gateway:latest`, refreshes unit files, and restarts `hermes-dee`.

- [ ] **Step 2: Verify the container user and mount**

Run: `/usr/bin/ssh totoro_ts 'sudo docker exec hermes-dee sh -lc "id && test -d /workspace/extra/obsidian && ls -ld /workspace/extra/obsidian"'`
Expected: PASS with uid `1000`, gid `1004`, and the Obsidian directory present.

- [ ] **Step 3: Verify write ownership in the mounted vault**

Run: `/usr/bin/ssh totoro_ts 'sudo docker exec hermes-dee sh -lc "rm -f /workspace/extra/obsidian/.hermes_mount_probe && touch /workspace/extra/obsidian/.hermes_mount_probe" && stat -c "%u:%g %n" /tank/personal/obsidian-personal/.hermes_mount_probe && rm -f /tank/personal/obsidian-personal/.hermes_mount_probe'`
Expected: `1000:1000 /tank/personal/obsidian-personal/.hermes_mount_probe`

- [ ] **Step 4: Run the full targeted test set**

Run: `python -m pytest tests/hermes_cli/test_totoro_deploy_config.py tests/integration/test_totoro_obsidian_mount_contract.py tests/e2e/test_totoro_obsidian_mount_contract.py -q`
Expected: PASS with pristine output
