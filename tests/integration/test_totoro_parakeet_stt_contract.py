from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
PARAKEET_BASE_URL = "http://172.17.0.1:8770"


def _load_yaml(path: str):
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def test_dee_parakeet_contract_is_consistent():
    dee_config = _load_yaml("deploy/config-dee.yaml")

    assert dee_config["stt"]["provider"] == "parakeet"
    assert dee_config["stt"]["parakeet"]["base_url"] == PARAKEET_BASE_URL
