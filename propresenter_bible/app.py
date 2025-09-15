"""Application orchestration (UI-bound).

This module wires the core library components together and manages user
interaction. It passes a ProgressReporter to the core layers but does not
handle progress display logic within the core modules.
"""

import shutil
from prompt_toolkit.shortcuts import radiolist_dialog
from .config import Config
from .services.api import BibleApiClient, VersionsResponse, VersionMetadata, VersionsItem
from .services.decoder import YvesDecoder
from .services.downloader import BibleDownloader
from .parsing.html_to_usx import HtmlToUsxParser
from .building.usx_builder import UsxBuilder
from .metadata.builder import MetadataBuilder
from .install.installer import get_installer, InstallerBase
from .ui.interface import Ui, ConsoleUi
from .progress import ConsoleProgressReporter
import click
from pathlib import Path


class BibleImportApp:
    def __init__(self, cfg: Config, ui: Ui | None = None):
        """Initialize the app with configuration and core services."""
        self.cfg = cfg
        self.api = BibleApiClient(cfg)
        self.decoder = YvesDecoder()
        self.downloader = BibleDownloader(self.api, self.decoder)
        self.parser = HtmlToUsxParser()
        self.usx = UsxBuilder(self.parser)
        self.meta = MetadataBuilder()
        self.installer: InstallerBase = get_installer()
        self.ui: Ui = ui or ConsoleUi()

    def run_interactive(self) -> None:
        """Run an interactive CLI workflow to import and install a Bible."""
        download_root = Path(self.cfg.download_dir)
        download_root.mkdir(parents=True, exist_ok=True)

        language = self._prompt_language()
        selected = self._prompt_version(language)
        metadata = self.api.get_version_metadata(selected.id)

        location = download_root / selected.local_abbreviation
        self._download_if_needed(location, selected, metadata)

        output_dir = Path(self.cfg.output_dir) / selected.local_abbreviation
        self._build_outputs(location, output_dir, metadata)
        self._install(output_dir, selected.local_abbreviation)

        print("Done! Please restart ProPresenter and check if the bible is correctly installed.")
        input("Press enter to close...")

    def _prompt_language(self) -> str:
        self.ui.info("Which language would you want to download?")
        return self.ui.choose_language(self.api)

    def _prompt_version(self, language: str) -> VersionsItem:
        versions: VersionsResponse = self.api.get_versions(language)
        by_id = {v.id: v for v in versions.versions}
        return self.ui.select_version(list(by_id.values()))

    def _download_if_needed(self, location: Path, version: VersionsItem, metadata: VersionMetadata, reporter=None) -> None:
        need_download = True if not location.exists() else self.ui.confirm(
            f"It appears that there is already a download folder for bible {version.local_abbreviation}. Are you sure you want to download the bible contents?"
        )
        if not need_download:
            return
        self.ui.info(f"Starting download {version.local_title}")
        location.mkdir(parents=True, exist_ok=True)
        rep = reporter or ConsoleProgressReporter()
        self.downloader.download(str(location), version.id, version.local_abbreviation, metadata, reporter=rep)

    def _build_outputs(self, location: Path, output_dir: Path, metadata: VersionMetadata, reporter=None) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.ui.info("Converting chapters to valid USX format")
        book_names = {b.usfm: b.human for b in metadata.books}
        rep = reporter or ConsoleProgressReporter()
        usx_out = output_dir / "USX_1"
        usx_out.mkdir(parents=True, exist_ok=True)
        self.usx.build_from_downloads(str(location), str(usx_out), book_names=book_names, reporter=rep)
        self.meta.build(str(output_dir), metadata)

    def _zip_bible_dir(self, output_dir: Path, abbr: str) -> str:
        zip_base = output_dir.parent / f"{abbr}.rvbible"
        shutil.make_archive(str(zip_base), 'zip', str(output_dir))
        return shutil.move(str(zip_base) + ".zip", str(zip_base))

    def _install(self, output_dir: Path, abbr: str) -> None:
        if self.installer.supports_overwrite:
            dialog = radiolist_dialog(
                "ProPresenter installation",
                "Choose how to install the Bible.",
                values=[(1, 'Overwrite (recommended)'), (0, 'Sideload')]
            )
            if dialog.run() == 1:
                # Interactive overwrite selection in UI layer
                choices = self.installer.get_available_overwrite_choices()
                from prompt_toolkit import prompt
                from .ui.prompting import PromptCompleter
                prompt_options = {f"{x['language']} - {x['name']}": x["displayAbbreviation"] for x in choices}
                self.ui.info("Which translation would you like to overwrite?")
                self.ui.info("Choose wisely - Please mind that you will not be able to use this translation anymore!")
                while True:
                    choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
                    choice_abbr = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower() or x[1].lower() == choice.lower()), None)
                    choice_biblemeta = next((x for x in choices if x["displayAbbreviation"].lower() == str(choice_abbr).lower()), None)
                    if choice_abbr is not None and choice_biblemeta is not None:
                        break
                    self.ui.warn("Please select one of the abbreviations from the list")
                self.installer.overwrite_free_bible(str(output_dir), choice_biblemeta["internalAbbreviation"])  # type: ignore[index]
                return

        rvbible_location = self._zip_bible_dir(output_dir, abbr)
        self.ui.info("Moving bible to ProPresenter directory")
        self.installer.move_rvbible_propresenter_folder(rvbible_location)

    # ---- Management (non-interactive) ----
    def list_installed(self):
        return self.installer.list_installed()

    def delete_installed(self, folder_id: str) -> None:
        self.installer.delete_installed(folder_id)

    def reassign_abbreviation(self, folder_id: str, new_internal_abbr: str) -> None:
        self.installer.reassign_abbreviation(folder_id, new_internal_abbr)
