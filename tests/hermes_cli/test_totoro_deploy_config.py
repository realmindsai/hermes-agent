from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OBSIDIAN_HOST_PATH = "/tank/personal/obsidian-personal"
OBSIDIAN_CONTAINER_PATH = "/workspace/extra/obsidian"
PARAKEET_BASE_URL = "http://172.17.0.1:8770"


def _load_yaml(path: str):
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_hermes_dee_uses_non_root_obsidian_mount():
    compose = _load_yaml("deploy/docker-compose.yaml")
    dee = compose["services"]["hermes-dee"]
    tracy = compose["services"]["hermes-tracy"]

    assert dee["user"] == "1000:1004"
    assert f"{OBSIDIAN_HOST_PATH}:{OBSIDIAN_CONTAINER_PATH}" in dee["volumes"]
    assert all(OBSIDIAN_CONTAINER_PATH not in volume for volume in tracy["volumes"])


def test_hermes_dee_cwd_points_at_obsidian_mount():
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee_config["terminal"]["cwd"] == OBSIDIAN_CONTAINER_PATH


def test_hermes_dee_uses_parakeet_stt():
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee_config["stt"]["provider"] == "parakeet"
    assert dee_config["stt"]["parakeet"]["base_url"] == PARAKEET_BASE_URL
