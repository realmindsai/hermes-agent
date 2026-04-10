import click
import uvicorn
from sqlalchemy import delete

from nutrition_service.api import create_app
from nutrition_service.db import create_engine_from_url, create_schema, create_session_factory
from nutrition_service.importers.fsanz import load_fsanz_rows, normalize_fsanz_row
from nutrition_service.importers.off import load_off_records, normalize_off_record
from nutrition_service.importers.usda import load_usda_foods, normalize_usda_food
from nutrition_service.models import SourceFoodFsanz, SourceFoodUsda, SourceProductOff
from nutrition_service.settings import NutritionSettings


@click.group()
def cli() -> None:
    """Nutrition service commands."""


@cli.command("migrate")
def migrate_command() -> None:
    settings = NutritionSettings()
    engine = create_engine_from_url(settings.database_url)
    try:
        create_schema(engine)
    finally:
        engine.dispose()
    click.echo(f"Migrated nutrition schema at {settings.database_url}")


@cli.command("import-off")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def import_off_command(json_path: str) -> None:
    settings = NutritionSettings()
    records = [normalize_off_record(row) for row in load_off_records(json_path)]
    engine = create_engine_from_url(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        create_schema(engine)
        with session_factory() as session:
            session.execute(delete(SourceProductOff))
            session.add_all(
                SourceProductOff(
                    barcode=row.barcode,
                    product_name=row.product_name,
                    brand_name=row.brand_name,
                    serving_size_text=row.serving_size_text,
                    energy_kcal=row.energy_kcal,
                    protein_g=row.protein_g,
                    carbs_g=row.carbs_g,
                    fat_g=row.fat_g,
                    nutriments_raw=row.raw_payload.get("nutriments"),
                    raw_payload=row.raw_payload,
                )
                for row in records
            )
            session.commit()
    finally:
        engine.dispose()
    click.echo(f"Imported {len(records)} Open Food Facts rows from {json_path}")


@cli.command("import-fsanz")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def import_fsanz_command(csv_path: str) -> None:
    settings = NutritionSettings()
    rows = [normalize_fsanz_row(row) for row in load_fsanz_rows(csv_path)]
    engine = create_engine_from_url(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        create_schema(engine)
        with session_factory() as session:
            session.execute(delete(SourceFoodFsanz))
            session.add_all(
                SourceFoodFsanz(
                    food_id=row.food_id,
                    food_name=row.food_name,
                    energy_kcal=row.energy_kcal,
                    protein_g=row.protein_g,
                    carbs_g=row.carbs_g,
                    fat_g=row.fat_g,
                    raw_payload=row.raw_payload,
                )
                for row in rows
            )
            session.commit()
    finally:
        engine.dispose()
    click.echo(f"Imported {len(rows)} FSANZ rows from {csv_path}")


@cli.command("import-usda")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def import_usda_command(json_path: str) -> None:
    settings = NutritionSettings()
    foods = [normalize_usda_food(food) for food in load_usda_foods(json_path)]
    engine = create_engine_from_url(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        create_schema(engine)
        with session_factory() as session:
            session.execute(delete(SourceFoodUsda))
            session.add_all(
                SourceFoodUsda(
                    fdc_id=food.fdc_id,
                    description=food.description,
                    gtin_upc=food.gtin_upc,
                    serving_size=food.serving_size,
                    serving_size_unit=food.serving_size_unit,
                    energy_kcal=food.energy_kcal,
                    protein_g=food.protein_g,
                    carbs_g=food.carbs_g,
                    fat_g=food.fat_g,
                    raw_payload=food.raw_payload,
                )
                for food in foods
            )
            session.commit()
    finally:
        engine.dispose()
    click.echo(f"Imported {len(foods)} USDA rows from {json_path}")


@cli.command("serve")
def serve_command() -> None:
    settings = NutritionSettings()
    uvicorn.run(create_app(), host=settings.bind_host, port=settings.bind_port)
