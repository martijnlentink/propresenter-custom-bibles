"""Domain model representing a single verse of Scripture."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Verse:
    number: str
    lines: List[str] = field(default_factory=list)

    def add_line(self, text: str) -> None:
        text = (text or "").strip()
        if text:
            self.lines.append(text)

    def text(self) -> str:
        return "\n".join(self.lines).strip()
