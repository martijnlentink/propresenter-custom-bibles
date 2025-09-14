"""CLI entrypoint to run the ProPresenter Bible importer interactively."""

from propresenter_bible import BibleImportApp, DEFAULT_CONFIG

if __name__ == '__main__':
    BibleImportApp(DEFAULT_CONFIG).run_interactive()
