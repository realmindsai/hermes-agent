import click


@click.group()
def cli() -> None:
    """Nutrition service commands."""


@cli.command("migrate")
def migrate_command() -> None:
    click.echo("migrate")


@cli.command("import-off")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def import_off_command(json_path: str) -> None:
    click.echo(f"import-off {json_path}")


@cli.command("import-fsanz")
@click.argument("csv_path", type=click.Path(exists=True, dir_okay=False))
def import_fsanz_command(csv_path: str) -> None:
    click.echo(f"import-fsanz {csv_path}")


@cli.command("import-usda")
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def import_usda_command(json_path: str) -> None:
    click.echo(f"import-usda {json_path}")


@cli.command("serve")
def serve_command() -> None:
    click.echo("serve")
