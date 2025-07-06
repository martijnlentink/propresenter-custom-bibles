import json
import os
import re
from typing import List

from dtos import InstalledBible


class ProPresenterBibleData:
    """Handle parsing and writing of the BibleData.proPref file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.entries: List[InstalledBible] = []
        self.load()

    def load(self) -> None:
        if not os.path.isfile(self.file_path):
            self.entries = []
            return
        with open(self.file_path, "r", encoding="utf-8") as handle:
            contents = handle.read()
        try:
            match = re.match(r"InstalledBiblesNew=(?P<array>\[[^\]]*?]);?", contents)
            data = json.loads(match.group("array")) if match else []
            self.entries = [self._parse_entry(x) for x in data]
        except Exception:
            self.entries = []

    def _parse_entry(self, meta: str) -> InstalledBible:
        parts = meta.split("|")
        return InstalledBible(parts[0], parts[1], parts[2], parts[3])

    def _entry_string(self, entry: InstalledBible) -> str:
        return "|".join([entry.id, entry.abbreviation, entry.translation, entry.bible_format])

    @property
    def abbreviations(self) -> set:
        return {e.abbreviation for e in self.entries}

    def add_entry(self, entry: InstalledBible) -> None:
        self.entries.append(entry)
        self.save()

    def save(self) -> None:
        arr = [self._entry_string(e) for e in self.entries]
        contents = "InstalledBiblesNew=" + json.dumps(arr) + ";\n"
        with open(self.file_path, "w", encoding="utf-8") as handle:
            handle.write(contents)
