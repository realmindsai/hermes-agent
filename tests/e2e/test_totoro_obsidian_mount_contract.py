from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_totoro_doc_describes_dee_obsidian_mount():
    doc = (REPO_ROOT / "deploy/totoro_hermes_gateway.md").read_text(encoding="utf-8")

    assert "/tank/personal/obsidian-personal" in doc
    assert "/workspace/extra/obsidian" in doc
    assert "1000:1004" in doc
    assert "hermes-dee" in doc
    assert "hermes-tracy" in doc
