import json
import lxml.html
from typing import Dict, List
from requests import get

from config import Config, DEFAULT_CONFIG
from dtos import (
    BibleMetadata,
    BibleVersion,
    BookInfo,
    ChapterContent,
    ChapterInfo,
    LanguageInfo,
    LanguageOption,
)


class BibleAPI:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config

    def get_api_id(self) -> str:
        landing_page_response = get("https://www.bible.com")
        html_page = lxml.html.fromstring(landing_page_response.text)
        next_data_script = html_page.xpath("//script[@id='__NEXT_DATA__']")
        next_data = json.loads(next_data_script[0].text)
        return next_data["buildId"]

    def get_languages(self) -> List[LanguageOption]:
        resp = get("https://www.bible.com/api/bible/configuration")
        data = resp.json()
        lang_versions = data["response"]["data"]["default_versions"]
        return [
            LanguageOption(
                language_tag=x["language_tag"],
                name=x["name"],
                local_name=x["local_name"],
            )
            for x in lang_versions
        ]

    def get_bible_versions(self, lang: str) -> Dict[int, BibleVersion]:
        resp = get(
            f"https://www.bible.com/api/bible/versions?language_tag={lang}&type=all",
            headers=self.config.headers,
        )
        data = resp.json()
        versions = data["response"]["data"]["versions"]
        return {
            v["id"]: BibleVersion(
                id=v["id"],
                title=v["title"],
                local_title=v["local_title"],
                abbreviation=v["abbreviation"],
                local_abbreviation=v["local_abbreviation"],
            )
            for v in versions
        }

    def get_bible_metadata(self, bible_id: int) -> BibleMetadata:
        resp = get(f"https://nodejs.bible.com/api/bible/version/3.3?id={bible_id}")
        data = resp.json()
        offline_url = data.get("offline", {}).get("url")
        language = data["language"]
        lang = LanguageInfo(
            iso_639_3=language["iso_639_3"],
            name=language["name"],
            text_direction=language["text_direction"],
        )
        books: List[BookInfo] = []
        for b in data.get("books", []):
            chapters = [ChapterInfo(usfm=c["usfm"]) for c in b.get("chapters", [])]
            books.append(
                BookInfo(
                    usfm=b["usfm"],
                    human=b["human"],
                    human_long=b["human_long"],
                    abbreviation=b["abbreviation"],
                    chapters=chapters,
                )
            )
        return BibleMetadata(
            title=data["title"],
            local_title=data["local_title"],
            abbreviation=data["abbreviation"],
            local_abbreviation=data["local_abbreviation"],
            language=lang,
            books=books,
            offline_url=offline_url,
        )

    def get_chapter(
        self,
        api_id: str,
        bible_id: int,
        usfm: str,
        abbr: str,
    ) -> ChapterContent:
        url = f"https://www.bible.com/_next/data/{api_id}/en/bible/{bible_id}/{usfm}.{abbr}.json"
        res = get(url, headers=self.config.headers)
        data = res.json()
        if "__N_REDIRECT" in data["pageProps"] or data["pageProps"]["chapterInfo"] is None:
            res = get(f"{url}?version={bible_id}&usfm={usfm}.{abbr}")
            data = res.json()
        filename = data["pageProps"]["params"]["usfm"]
        contents = data["pageProps"]["chapterInfo"]["content"]
        next_obj = data["pageProps"]["chapterInfo"].get("next")
        next_usfm = next_obj["usfm"][0] if next_obj is not None else None
        return ChapterContent(filename=filename, content=contents, next_usfm=next_usfm)

    def download_offline_zip(self, offline_url: str) -> bytes:
        response = get(f"https:{offline_url}")
        return response.content
