"""HTTP client for bible.com endpoints with typed dataclass responses."""

from __future__ import annotations

import json
import lxml.html
from dataclasses import dataclass
from typing import Optional, List
from requests import get
from ..config import Config


# Dataclass response models (subset of fields used by the app)

@dataclass
class LanguagesItem:
    language_tag: str
    name: str
    local_name: str

    @staticmethod
    def from_dict(d: dict) -> LanguagesItem:
        return LanguagesItem(
            language_tag=d.get("language_tag", ""),
            name=d.get("name", ""),
            local_name=d.get("local_name", ""),
        )


@dataclass
class LanguagesResponse:
    default_versions: List[LanguagesItem]

    @staticmethod
    def from_dict(d: dict) -> LanguagesResponse:
        items = d.get("response", {}).get("data", {}).get("default_versions", [])
        return LanguagesResponse(default_versions=[LanguagesItem.from_dict(x) for x in items])


@dataclass
class VersionsItem:
    id: int
    local_title: str
    local_abbreviation: str

    @staticmethod
    def from_dict(d: dict) -> VersionsItem:
        return VersionsItem(
            id=int(d.get("id")),
            local_title=d.get("local_title", ""),
            local_abbreviation=d.get("local_abbreviation", ""),
        )


@dataclass
class VersionsResponse:
    versions: List[VersionsItem]

    @staticmethod
    def from_dict(d: dict) -> VersionsResponse:
        items = d.get("response", {}).get("data", {}).get("versions", [])
        return VersionsResponse(versions=[VersionsItem.from_dict(x) for x in items])


@dataclass
class VersionBookChapter:
    usfm: str

    @staticmethod
    def from_dict(d: dict) -> VersionBookChapter:
        return VersionBookChapter(usfm=d.get("usfm", ""))


@dataclass
class VersionBook:
    usfm: str
    abbreviation: str
    human: str
    human_long: str
    canon: Optional[str]
    chapters: List[VersionBookChapter]

    @staticmethod
    def from_dict(d: dict) -> VersionBook:
        return VersionBook(
            usfm=d.get("usfm", ""),
            abbreviation=d.get("abbreviation", ""),
            human=d.get("human", ""),
            human_long=d.get("human_long", ""),
            canon=d.get("canon"),
            chapters=[VersionBookChapter.from_dict(x) for x in d.get("chapters", [])],
        )


@dataclass
class VersionLanguage:
    iso_639_3: str
    name: str
    text_direction: str

    @staticmethod
    def from_dict(d: dict) -> VersionLanguage:
        return VersionLanguage(
            iso_639_3=d.get("iso_639_3", ""),
            name=d.get("name", ""),
            text_direction=d.get("text_direction", ""),
        )


@dataclass
class VersionOffline:
    url: str

    @staticmethod
    def from_dict(d: dict) -> VersionOffline:
        return VersionOffline(url=d.get("url", ""))


@dataclass
class VersionMetadata:
    id: Optional[int]
    title: str
    local_title: str
    abbreviation: str
    local_abbreviation: str
    language: VersionLanguage
    books: List[VersionBook]
    offline: Optional[VersionOffline]

    @staticmethod
    def from_dict(d: dict) -> VersionMetadata:
        return VersionMetadata(
            id=d.get("id"),
            title=d.get("title", ""),
            local_title=d.get("local_title", ""),
            abbreviation=d.get("abbreviation", ""),
            local_abbreviation=d.get("local_abbreviation", ""),
            language=VersionLanguage.from_dict(d.get("language", {})),
            books=[VersionBook.from_dict(x) for x in d.get("books", [])],
            offline=VersionOffline.from_dict(d["offline"]) if d.get("offline") else None,
        )


# Next.js chapter page response (subset)

@dataclass
class ChapterNext:
    usfm: List[str]

    @staticmethod
    def from_dict(d: dict) -> ChapterNext:
        return ChapterNext(usfm=list(d.get("usfm", [])))


@dataclass
class ChapterReference:
    human: str

    @staticmethod
    def from_dict(d: dict) -> ChapterReference:
        return ChapterReference(human=d.get("human", ""))


@dataclass
class ChapterInfo:
    content: str
    next: Optional[ChapterNext]
    reference: ChapterReference

    @staticmethod
    def from_dict(d: dict) -> ChapterInfo:
        return ChapterInfo(
            content=d.get("content", ""),
            next=ChapterNext.from_dict(d["next"]) if d.get("next") else None,
            reference=ChapterReference.from_dict(d.get("reference", {})),
        )


@dataclass
class ChapterParams:
    usfm: str

    @staticmethod
    def from_dict(d: dict) -> ChapterParams:
        return ChapterParams(usfm=d.get("usfm", ""))


@dataclass
class ChapterPageProps:
    params: ChapterParams
    chapterInfo: ChapterInfo

    @staticmethod
    def from_dict(d: dict) -> ChapterPageProps:
        return ChapterPageProps(
            params=ChapterParams.from_dict(d.get("params", {})),
            chapterInfo=ChapterInfo.from_dict(d.get("chapterInfo", {})),
        )


@dataclass
class ChapterPage:
    pageProps: ChapterPageProps

    @staticmethod
    def from_dict(d: dict) -> ChapterPage:
        return ChapterPage(pageProps=ChapterPageProps.from_dict(d.get("pageProps", {})))


class BibleApiClient:
    """Typed HTTP client wrapping bible.com endpoints.

    Only a subset of fields are modeled, namely those used by the importer.
    """

    def __init__(self, config: Config, http_get=get):
        self._cfg = config
        self._get = http_get

    def get_languages_config(self) -> LanguagesResponse:
        """Return configuration including default_versions per language."""
        raw = self._get("https://www.bible.com/api/bible/configuration").json()
        return LanguagesResponse.from_dict(raw)

    def get_versions(self, lang: str) -> VersionsResponse:
        """Return available versions for a given language tag."""
        url = f"https://www.bible.com/api/bible/versions?language_tag={lang}&type=all"
        raw = self._get(url, headers=self._cfg.headers).json()
        return VersionsResponse.from_dict(raw)

    def get_build_id(self) -> str:
        """Return Next.js build id needed to fetch chapter JSON."""
        landing_page_response = self._get("https://www.bible.com")
        html_page = lxml.html.fromstring(landing_page_response.text)
        next_data_script = html_page.xpath("//script[@id='__NEXT_DATA__']")
        next_data = json.loads(next_data_script[0].text)
        return next_data["buildId"]

    def get_version_metadata(self, book_id: int) -> VersionMetadata:
        """Return version metadata used to build USX and metadata files."""
        raw = self._get(f"https://nodejs.bible.com/api/bible/version/3.3?id={book_id}").json()
        return VersionMetadata.from_dict(raw)

    def get_chapter_page(self, build_id: str, version_id: int, usfm: str, abbr: str) -> ChapterPage:
        """Return chapter pageProps JSON for a given USFM and version."""
        url = f"https://www.bible.com/_next/data/{build_id}/en/bible/{version_id}/{usfm}.{abbr}.json"
        res = self._get(url, headers=self._cfg.headers)
        data = res.json()
        if "__N_REDIRECT" in data.get("pageProps", {}) or (data.get("pageProps", {}).get("chapterInfo") is None):
            res = self._get(f"{url}?version={version_id}&usfm={usfm}.{abbr}")
            data = res.json()
        return ChapterPage.from_dict(data)
