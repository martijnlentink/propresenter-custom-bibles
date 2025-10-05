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


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """ProPresenter Bible tools.

    If no subcommand is provided, the GUI is launched.
    """
    if ctx.invoked_subcommand is None:
        try:
            from propresenter_bible.gui.app_gui import run_gui
            run_gui()
        except Exception as e:
            click.echo(f"Failed to launch GUI: {e}")


@cli.command(name="install")
def import_bible_cmd():
    """Run interactive download/import flow."""
    BibleImportApp(DEFAULT_CONFIG).run_interactive()


@cli.group(name="manage")
def manage_cmd():
    """Manage installed custom bibles."""
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


@cli.command(name="gui")
def gui_cmd():
    """Launch the GUI."""
    try:
        from propresenter_bible.gui.app_gui import run_gui
        run_gui()
    except Exception as e:
        click.echo(f"Failed to launch GUI: {e}")


@cli.command(name="backup")
@click.option("--dest", "dest", required=False, help="Destination folder for backup")
def backup_cmd(dest: str | None = None):
    """Back up current ProPresenter Bible state to a folder."""
    app = BibleImportApp(DEFAULT_CONFIG)
    app.backup(dest)

@cli.command(name="restore")
@click.option("--src", "src", required=True, help="Path to backup folder to restore from")
@click.option("--overwrite/--no-overwrite", default=False, help="Overwrite existing files when restoring")
def restore_cmd(src: str, overwrite: bool):
    """Restore a previously backed up Bible state from a folder."""
    app = BibleImportApp(DEFAULT_CONFIG)
    app.restore(src, overwrite=overwrite)

@cli.command(name="cleanup-dangling")
def cleanup_dangling_cmd():
    """Clean up dangling installed bibles (Windows only)."""
    app = BibleImportApp(DEFAULT_CONFIG)
    app.cleanup_dangling()


if __name__ == '__main__':
    cli()
