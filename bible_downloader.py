import html
import io
import os
import pathlib
import time
import zipfile
from typing import Dict, List, Optional

from tqdm import tqdm

from config import Config, DEFAULT_CONFIG
from dtos import BibleMetadata, BibleVersion, LanguageOption
from utils import read_yves_file
from bible_api import BibleAPI


class BibleDownloader:
    def __init__(self, api: BibleAPI, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.api = api

    def retrieve_api_id(self) -> str:
        return self.api.get_api_id()

    def retrieve_languages(self) -> List[LanguageOption]:
        return self.api.get_languages()

    def retrieve_bibles_for_language(self, lang: str) -> Dict[int, BibleVersion]:
        return self.api.get_bible_versions(lang)

    def retrieve_bible_metadata(self, book_id: int) -> BibleMetadata:
        return self.api.get_bible_metadata(book_id)


    def download_bible_chapters(
        self,
        location: str,
        selected_bible_id: int,
        selected_bible_abbr: str,
        bible_metadata: BibleMetadata,
    ) -> None:
        offline_url = bible_metadata.offline_url
        if offline_url:
            zip_bytes = self.api.download_offline_zip(offline_url)
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
            yves_zip = os.path.join(location, "yves")
            zip_file.extractall(yves_zip)
            for yves_chapter_file in tqdm(pathlib.Path(yves_zip).rglob("*.yves"), desc="Decode Yves files to HTML"):
                decoded_data = read_yves_file(yves_chapter_file)
                chapter_name = yves_chapter_file.parent.name
                chapter_num = yves_chapter_file.name.split(".")[0]
                chapter_identifier = f"{chapter_name}.{chapter_num}"
                with open(os.path.join(location, chapter_identifier), "w", encoding="utf-8") as file:
                    file.writelines(decoded_data)
        else:
            next_chapter: Optional[str] = bible_metadata.books[0].chapters[0].usfm
            retries = 5
            api_id = self.retrieve_api_id()
            while next_chapter is not None:
                try:
                    print(f"Retrieving bible chapter: {next_chapter}".ljust(40), end="\r", flush=True)
                    chapter = self.api.get_chapter(api_id, selected_bible_id, next_chapter, selected_bible_abbr)
                    with open(os.path.join(location, chapter.filename), "w", encoding="utf-8") as file:
                        file.writelines(html.unescape(chapter.content))
                    next_chapter = chapter.next_usfm
                except Exception:
                    retries -= 1
                    if retries > 0:
                        time.sleep(5)
                    else:
                        raise

