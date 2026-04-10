"""E2E contract tests for nutrition service bootstrap behavior."""

from click.testing import CliRunner
from sqlalchemy import create_engine, text

from nutrition_service.cli import cli


def _row_count(database_url: str, table_name: str) -> int:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    finally:
        engine.dispose()


def test_import_off_replaces_previous_seed_rows(tmp_path, monkeypatch):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'nutrition.sqlite3'}"
    monkeypatch.setenv("NUTRITION_SERVICE_DATABASE_URL", database_url)
    first_path = tmp_path / "off-first.json"
    first_path.write_text(
        '[{"code":"930000000001","product_name":"Bar One"}]',
        encoding="utf-8",
    )
    second_path = tmp_path / "off-second.json"
    second_path.write_text(
        '[{"code":"930000000002","product_name":"Bar Two"},{"code":"930000000003","product_name":"Bar Three"}]',
        encoding="utf-8",
    )
    runner = CliRunner()

    migrate = runner.invoke(cli, ["migrate"])
    first_import = runner.invoke(cli, ["import-off", str(first_path)])
    second_import = runner.invoke(cli, ["import-off", str(second_path)])

    assert migrate.exit_code == 0
    assert first_import.exit_code == 0
    assert second_import.exit_code == 0
    assert "Imported 1 Open Food Facts rows" in first_import.output
    assert "Imported 2 Open Food Facts rows" in second_import.output
    assert _row_count(database_url, "source_product_off") == 2
