"""Domain model representing a paragraph which may contain verses or text."""

from dataclasses import dataclass, field
from typing import List, Optional
from .verse import Verse


@dataclass
class Paragraph:
    style: str
    verses: List[Verse] = field(default_factory=list)
    text: Optional[str] = None  # for headings and raw text paras

    def add_verse(self, verse: Verse) -> None:
        self.verses.append(verse)

    def add_text_line(self, line: str) -> None:
        current = (self.text or "").strip()
        line = (line or "").strip()
        if not line:
            return
        self.text = (f"{current}\n{line}" if current else line)
