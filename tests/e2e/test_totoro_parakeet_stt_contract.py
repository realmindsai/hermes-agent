from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_totoro_doc_describes_dee_parakeet_stt():
    doc = (REPO_ROOT / "deploy/totoro_docker_install.md").read_text(encoding="utf-8")

    assert "parakeet-stt" in doc
    assert "http://127.0.0.1:8770" in doc
    assert "http://172.17.0.1:8770" in doc
    assert "hermes-dee" in doc
