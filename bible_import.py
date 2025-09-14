"""CLI entrypoint for the ProPresenter Bible importer/manager.

Usage examples:
  - Download/import interactively:
      python bible_import.py import-bible

  - List installed custom bibles (Windows):
      python bible_import.py manage list

  - Delete an installed bible by folder id:
      python bible_import.py manage delete --id <folder_id>

  - Reassign installed bible to a different internal abbreviation:
      python bible_import.py manage reassign --id <folder_id> --abbr <ABBR>
"""

import click
from propresenter_bible import BibleImportApp, DEFAULT_CONFIG


@click.group()
def cli():
    """ProPresenter Bible tools."""
    pass


@cli.command(name="import-bible")
def import_bible_cmd():
    """Run interactive download/import flow."""
    BibleImportApp(DEFAULT_CONFIG).run_interactive()


@cli.group(name="manage")
def manage_cmd():
    """Manage installed custom bibles (Windows)."""
    pass


@manage_cmd.command(name="list")
def manage_list_cmd():
    app = BibleImportApp(DEFAULT_CONFIG)
    try:
        entries = app.list_installed()
    except NotImplementedError:
        click.echo("Management operations are not supported on this platform.")
        return
    if not entries:
        click.echo("No installed custom bibles found.")
        return
    for e in entries:
        click.echo(f"id={e.folder_id} abbr={e.abbreviation} name={e.name} format={e.bible_format}")


@manage_cmd.command(name="delete")
@click.option("--id", "folder_id", required=True, help="Folder id of installed bible to delete")
def manage_delete_cmd(folder_id: str):
    app = BibleImportApp(DEFAULT_CONFIG)
    try:
        app.delete_installed(folder_id)
        click.echo(f"Deleted installed bible {folder_id}")
    except NotImplementedError:
        click.echo("Delete operation is not supported on this platform.")


@manage_cmd.command(name="reassign")
@click.option("--id", "folder_id", required=True, help="Folder id of installed bible")
@click.option("--abbr", "new_abbr", required=True, help="New internal abbreviation to assign")
def manage_reassign_cmd(folder_id: str, new_abbr: str):
    app = BibleImportApp(DEFAULT_CONFIG)
    try:
        app.reassign_abbreviation(folder_id, new_abbr)
        click.echo(f"Reassigned {folder_id} to abbreviation {new_abbr}")
    except NotImplementedError:
        click.echo("Reassign operation is not supported on this platform.")
    except ValueError as ve:
        click.echo(f"Error: {ve}")


if __name__ == '__main__':
    cli()
