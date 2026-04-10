import click


@click.group()
def cli() -> None:
    """Nutrition service commands."""


@cli.command("migrate")
def migrate_command() -> None:
    click.echo("migrate")


@cli.command("import-off")
def import_off_command() -> None:
    click.echo("import-off")


@cli.command("import-fsanz")
def import_fsanz_command() -> None:
    click.echo("import-fsanz")


@cli.command("import-usda")
def import_usda_command() -> None:
    click.echo("import-usda")


@cli.command("serve")
def serve_command() -> None:
    click.echo("serve")

