from dataclasses import dataclass
from typing import List, Optional

@dataclass
class LanguageOption:
    language_tag: str
    name: str
    local_name: str

    @property
    def display(self) -> str:
        return self.local_name if self.local_name == self.name else f"{self.local_name} ({self.name})"

@dataclass
class BibleVersion:
    id: int
    title: str
    local_title: str
    abbreviation: str
    local_abbreviation: str

@dataclass
class ChapterInfo:
    usfm: str

@dataclass
class BookInfo:
    usfm: str
    human: str
    human_long: str
    abbreviation: str
    chapters: List[ChapterInfo]

@dataclass
class LanguageInfo:
    iso_639_3: str
    name: str
    text_direction: str

@dataclass
class BibleMetadata:
    title: str
    local_title: str
    abbreviation: str
    local_abbreviation: str
    language: LanguageInfo
    books: List[BookInfo]
    offline_url: Optional[str] = None

@dataclass
class ChapterContent:
    filename: str
    content: str
    next_usfm: Optional[str]


@dataclass
class InstalledBible:
    id: str
    abbreviation: str
    translation: str
    bible_format: str
