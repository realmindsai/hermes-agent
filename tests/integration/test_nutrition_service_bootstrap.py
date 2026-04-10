"""Integration tests for nutrition service dataset bootstrap commands."""

from pathlib import Path

from click.testing import CliRunner
from sqlalchemy import create_engine, text

from nutrition_service.cli import cli


def _count_rows(database_path: Path, table_name: str) -> int:
    engine = create_engine(f"sqlite+pysqlite:///{database_path}")
    try:
        with engine.connect() as connection:
            return connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    finally:
        engine.dispose()


def test_cli_bootstrap_seeds_all_source_tables(tmp_path, monkeypatch):
    database_path = tmp_path / "nutrition.sqlite3"
    monkeypatch.setenv(
        "NUTRITION_SERVICE_DATABASE_URL",
        f"sqlite+pysqlite:///{database_path}",
    )
    off_path = tmp_path / "off.json"
    off_path.write_text(
        '[{"code":"930000000001","product_name":"Test Bar","brands":"Test Brand","nutriments":{"energy-kcal_serving":210}}]',
        encoding="utf-8",
    )
    fsanz_path = tmp_path / "fsanz.csv"
    fsanz_path.write_text(
        "Food ID,Food Name,Energy, kcal,Protein, g,Carbohydrate, g,Fat, g\nA001,Boiled egg,155,12.6,1.1,11.0\n",
        encoding="utf-8",
    )
    usda_path = tmp_path / "usda.json"
    usda_path.write_text(
        '[{"fdcId":123,"description":"Protein Bar","gtinUpc":"008181234567","servingSize":50,"servingSizeUnit":"g","foodNutrients":[{"nutrientName":"Energy","unitName":"KCAL","value":205}]}]',
        encoding="utf-8",
    )
    runner = CliRunner()

    migrate = runner.invoke(cli, ["migrate"])
    import_off = runner.invoke(cli, ["import-off", str(off_path)])
    import_fsanz = runner.invoke(cli, ["import-fsanz", str(fsanz_path)])
    import_usda = runner.invoke(cli, ["import-usda", str(usda_path)])

    assert migrate.exit_code == 0
    assert import_off.exit_code == 0
    assert import_fsanz.exit_code == 0
    assert import_usda.exit_code == 0
    assert _count_rows(database_path, "source_product_off") == 1
    assert _count_rows(database_path, "source_food_fsanz") == 1
    assert _count_rows(database_path, "source_food_usda") == 1
