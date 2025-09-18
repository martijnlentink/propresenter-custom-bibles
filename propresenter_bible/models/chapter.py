"""Domain model representing a chapter containing paragraphs/verses."""

from dataclasses import dataclass, field
from typing import List, Iterator, Optional
from .paragraph import Paragraph


@dataclass
class Chapter:
    number: str
    paragraphs: List[Paragraph] = field(default_factory=list)

    def add_paragraph(self, para: Paragraph) -> None:
        self.paragraphs.append(para)

    def iter_verses(self) -> Iterator[tuple[str, str]]:
        for p in self.paragraphs:
            for v in p.verses:
                yield v.number, v.text()

    def get_verse(self, number: str) -> Optional[str]:
        for vn, text in self.iter_verses():
            if str(vn) == str(number):
                return text
        return None
