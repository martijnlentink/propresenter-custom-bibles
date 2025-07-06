import json
import os
import platform
import shutil
from uuid import uuid4

from lxml import etree as ElementTree
from lxml.etree import tostring
from prompt_toolkit import prompt

from config import Config, DEFAULT_CONFIG
from utils import PromptCompleter, resource_path
from propresenter_bible_data import ProPresenterBibleData
from dtos import InstalledBible


class ProPresenterInstaller:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config

    def move_rvbible_propresenter_folder(self, rvbible_loc: str):
        system_str = platform.system()
        _, filename = os.path.split(rvbible_loc)
        if system_str == 'Windows':
            program_data = os.getenv('PROGRAMDATA')
            propresenter_bible_location = os.path.join(program_data, 'RenewedVision\\ProPresenter\\Bibles\\sideload')
            os.makedirs(propresenter_bible_location, exist_ok=True)
        elif system_str == 'Darwin':
            propresenter_bible_location = '/Library/Application Support/RenewedVision/RVBibles/v2/'
        else:
            raise Exception("Unable to determine operating system, please copy the bible manually")
        new_file_loc = os.path.join(propresenter_bible_location, filename)
        shutil.copyfile(rvbible_loc, new_file_loc)

    def overwrite_free_bible(self, bible_folder: str):
        program_data = os.getenv('PROGRAMDATA')

        with open(resource_path("available_bibles.json"), "r", encoding="utf-8") as free_bibles:
            free_bibles_json = json.load(free_bibles)

        propresenter_bible_location = os.path.join(program_data, 'RenewedVision\\ProPresenter\\Bibles')
        bible_data_propref_loc = os.path.join(propresenter_bible_location, "BibleData.proPref")
        store = ProPresenterBibleData(bible_data_propref_loc)

        prompt_options = {
            f'{x["language"]} - {x["name"]}': x["displayAbbreviation"]
            for x in free_bibles_json
            if x["internalAbbreviation"] not in store.abbreviations
        }
        print("Which translation would you like to overwrite?")
        print("Choose wisely - Please mind that you will not be able to use this translation anymore!")
        while True:
            choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
            choice_abbr = next(
                (x[1] for x in prompt_options.items() if x[0].lower() == choice.lower() or x[1].lower() == choice.lower()),
                None,
            )
            choice_biblemeta = next((x for x in free_bibles_json if x["displayAbbreviation"].lower() == str(choice_abbr).lower()), None)
            if choice_abbr is not None and choice_biblemeta is not None:
                break
            print("Please select one of the abbreviations from the list")

        overwrite_abbr = choice_biblemeta["internalAbbreviation"]
        folder_id = str(uuid4())
        new_bible_folder = os.path.join(propresenter_bible_location, folder_id)
        shutil.move(bible_folder, new_bible_folder)
        rvmetadata = os.path.join(new_bible_folder, "rvmetadata.xml")
        xtree = ElementTree.parse(rvmetadata)
        abbr_tag = xtree.xpath("//abbreviation")[0]
        name = xtree.xpath("//name")[0].text
        abbr_tag.text = overwrite_abbr
        with open(rvmetadata, 'wb') as rvmetadata_handle:
            rvmetadata_handle.write(tostring(xtree, encoding='utf-8'))

        store.add_entry(InstalledBible(folder_id, overwrite_abbr, name, "1"))

