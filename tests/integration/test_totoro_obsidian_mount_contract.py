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
    tracy = compose["services"]["hermes-tracy"]
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee["user"] == "1000:1004"
    assert f"{OBSIDIAN_HOST_PATH}:{OBSIDIAN_CONTAINER_PATH}" in dee["volumes"]
    assert dee_config["terminal"]["cwd"] == OBSIDIAN_CONTAINER_PATH
    assert all(OBSIDIAN_CONTAINER_PATH not in volume for volume in tracy["volumes"])
