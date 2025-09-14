"""Domain model representing a Bible book with multiple chapters."""

from dataclasses import dataclass, field
from typing import List, Optional
from .chapter import Chapter


@dataclass
class Book:
    code: str
    name: Optional[str] = None
    chapters: List[Chapter] = field(default_factory=list)

    def add_chapter(self, chapter: Chapter) -> None:
        self.chapters.append(chapter)

    def get_chapter(self, number: str) -> Optional[Chapter]:
        for ch in self.chapters:
            if str(ch.number) == str(number):
                return ch
        return None
