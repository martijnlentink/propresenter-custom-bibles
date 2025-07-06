import os
import platform
import shutil

import click
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

from config import Config, DEFAULT_CONFIG
from bible_api import BibleAPI
from bible_downloader import BibleDownloader
from bible_converter import BibleConverter
from propresenter_installer import ProPresenterInstaller
from utils import PromptCompleter


class BibleImportCLI:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.api = BibleAPI(config)
        self.downloader = BibleDownloader(self.api, config)
        self.converter = BibleConverter(config)
        self.installer = ProPresenterInstaller(config)

    def choose_language(self) -> str:
        languages = self.downloader.retrieve_languages()
        prompt_options = {lang.display: lang.language_tag for lang in languages}
        print("Choose the language you want to retrieve")
        while True:
            choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
            lang_code = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower()), None)
            if lang_code is not None:
                return lang_code
            print("Please select a valid language from the list. Press TAB to select.")

    def run(self):
        os.makedirs(self.config.download_folder, exist_ok=True)
        click.echo("Which language would you want to download?")
        language = self.choose_language()
        available_bibles = self.downloader.retrieve_bibles_for_language(language)
        options_response_str = '\n'.join(
            [f"{x.id}: {x.local_title} ({x.local_abbreviation})" for x in available_bibles.values()]
        )
        print(options_response_str)
        selected_bible_id = click.prompt("Please select the number above to download the scripture", type=int)
        selected_bible = available_bibles[selected_bible_id]
        selected_bible_abbr = selected_bible.local_abbreviation
        print("Retrieve bible metadata")
        bible_metadata = self.downloader.retrieve_bible_metadata(selected_bible_id)
        location = os.path.join(self.config.download_folder, selected_bible_abbr)
        download_required = not os.path.exists(location) or click.confirm(
            f"It appears that there is already a download folder for bible {selected_bible_abbr}. Are you sure you want to download the bible contents?"
        )
        if download_required:
            os.makedirs(location, exist_ok=True)
            print(f"Starting download {selected_bible.local_title}")
            self.downloader.download_bible_chapters(location, selected_bible_id, selected_bible_abbr, bible_metadata)
        output_folder = os.path.join(self.config.output_folder, selected_bible_abbr)
        usx_folder = os.path.join(output_folder, "USX_1")
        os.makedirs(usx_folder, exist_ok=True)
        print("Converting chapters to valid USX format")
        self.converter.process_bible_files(location, usx_folder)
        self.converter.construct_metadataxmls(output_folder, bible_metadata.__dict__)
        dialog = radiolist_dialog(
            "ProPresenter for Windows has two options to load bibles",
            "1. Overwriting a free bible (Recommended) - The bible that was just downloaded will overwrite this Bible\n2. Sideloading the Bible (Only for advanced users) - This will make sure ProPresenter will load the Bible upon startup. Disadvantages are; potential disk storage leaks and existing bibles might go missing.",
            values=[(1, 'Overwrite (recommended)'), (0, 'Sideload')],
        )
        if platform.system() == "Windows" and dialog.run() == 1:
            self.installer.overwrite_free_bible(output_folder)
        else:
            zip_location = os.path.join(output_folder, f"../{selected_bible_abbr}.rvbible")
            shutil.make_archive(zip_location, 'zip', output_folder)
            rvbible_location = shutil.move(zip_location + ".zip", zip_location)
            print("Moving bible to ProPresenter directory")
            self.installer.move_rvbible_propresenter_folder(rvbible_location)
        print("Done! Please restart ProPresenter and check if the bible is correctly installed.")
        input("Press enter to close...")

