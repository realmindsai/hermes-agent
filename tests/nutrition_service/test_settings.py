from click.testing import CliRunner

from nutrition_service.cli import cli
from nutrition_service.settings import NutritionSettings


def test_settings_read_database_and_bind_env(monkeypatch):
    monkeypatch.setenv(
        "NUTRITION_SERVICE_DATABASE_URL",
        "postgresql+psycopg://nutrition:secret@localhost:6543/custom_nutrition",
    )
    monkeypatch.setenv("NUTRITION_SERVICE_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("NUTRITION_SERVICE_BIND_PORT", "9999")

    settings = NutritionSettings()

    assert settings.database_url == "postgresql+psycopg://nutrition:secret@localhost:6543/custom_nutrition"
    assert settings.bind_host == "0.0.0.0"
    assert settings.bind_port == 9999


def test_cli_lists_expected_commands():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "migrate" in result.output
    assert "import-off" in result.output
    assert "import-fsanz" in result.output
    assert "import-usda" in result.output
    assert "serve" in result.output
