"""ProPresenter installation helpers (UI-agnostic).

Provides an OS-specific installer selected via a factory. Core code should not
depend on the OS directly; instead, call `get_installer()` to obtain an
installer instance for the current platform.
"""

import json
import platform
import re
from uuid import uuid4
from typing import TypedDict, List, Optional, Iterable
from dataclasses import dataclass
from pathlib import Path
from lxml import etree as ElementTree
from ..resources import resource_path, toxml


class FreeBibleMeta(TypedDict):
    language: str
    name: str
    displayAbbreviation: str
    internalAbbreviation: str


class InstallerBase:
    """Base installer with common helpers and abstract operations."""

    supports_overwrite: bool = False  # overridden on platforms that support overwrite

    # ---------- Common, OS-agnostic helpers ----------
    def load_free_bibles(self) -> List[FreeBibleMeta]:
        """Return metadata for free bibles that can be overwritten."""
        path = Path(resource_path("available_bibles.json"))
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def parse_bible_meta(entry: str) -> dict:
        """Parse a single InstalledBiblesNew entry into dict fields."""
        parts = entry.split('|')
        return {"id": parts[0], "abbreviation": parts[1], "translation": parts[2], "bible_format": parts[3]}

    # ---------- Abstract/OS-specific operations ----------
    def get_sideload_dir(self) -> Path:
        raise NotImplementedError

    def get_bibles_root_dir(self) -> Optional[Path]:
        """Root dir where BibleData.proPref lives (if applicable to the OS)."""
        return None

    def move_rvbible_propresenter_folder(self, rvbible_loc: str) -> None:
        dest_dir = self.get_sideload_dir()
        dest_dir.mkdir(parents=True, exist_ok=True)
        src = Path(rvbible_loc)
        dest = dest_dir / src.name
        dest.write_bytes(Path(rvbible_loc).read_bytes())

    def read_installed_bibledata(self) -> List[str]:
        """Read the BibleData.proPref installed entries; returns raw entries list."""
        return []

    def get_available_overwrite_choices(self) -> List[FreeBibleMeta]:
        installed_raw = self.read_installed_bibledata()
        installed_meta = [self.parse_bible_meta(x) for x in installed_raw]
        used_abbreviations = set(x["abbreviation"] for x in installed_meta)
        return [x for x in self.load_free_bibles() if x["internalAbbreviation"] not in used_abbreviations]

    def overwrite_free_bible(self, bible_folder: str, overwrite_internal_abbr: str) -> None:
        raise NotImplementedError("Overwrite is not supported on this platform")

    # ---------- Management operations (optional per platform) ----------
    def list_installed(self) -> List["InstalledBibleEntry"]:
        """Return a list of installed custom bibles (if supported)."""
        return []

    def delete_installed(self, folder_id: str) -> None:
        """Delete an installed custom bible by its folder id (if supported)."""
        raise NotImplementedError("Delete not supported on this platform")

    def reassign_abbreviation(self, folder_id: str, new_internal_abbr: str) -> None:
        """Change the internal abbreviation of an installed bible (if supported)."""
        raise NotImplementedError("Reassign not supported on this platform")


@dataclass
class InstalledBibleEntry:
    """Represents an entry in BibleData.proPref for a custom installed bible."""
    folder_id: str
    abbreviation: str
    name: str
    bible_format: str


class WindowsInstaller(InstallerBase):
    """Installer implementation for Windows."""

    supports_overwrite = True

    def get_sideload_dir(self) -> Path:
        import os as _os
        base = _os.getenv('PROGRAMDATA')
        if not base:
            raise RuntimeError("PROGRAMDATA environment variable not set")
        return Path(base) / 'RenewedVision' / 'ProPresenter' / 'Bibles' / 'sideload'

    def get_bibles_root_dir(self) -> Optional[Path]:
        import os as _os
        base = _os.getenv('PROGRAMDATA')
        return Path(base) / 'RenewedVision' / 'ProPresenter' / 'Bibles' if base else None

    def read_installed_bibledata(self) -> List[str]:
        root = self.get_bibles_root_dir()
        if not root:
            return []
        pref = root / 'BibleData.proPref'
        if not pref.is_file():
            return []
        try:
            contents = pref.read_text(encoding='utf-8')
            match = re.match(r"InstalledBiblesNew=(?P<array>\[[^\]]*?]);?", contents)
            return json.loads(match.group("array")) if match else []
        except Exception:
            return []

    def overwrite_free_bible(self, bible_folder: str, overwrite_internal_abbr: str) -> None:
        root = self.get_bibles_root_dir()
        if not root:
            raise RuntimeError("Bibles root directory not found")

        # Move bible to new folder id
        folder_id = str(uuid4())
        new_bible_folder = root / folder_id
        Path(bible_folder).rename(new_bible_folder)

        # Adjust rvmetadata abbreviation
        rvmetadata = new_bible_folder / "rvmetadata.xml"
        xtree = ElementTree.parse(str(rvmetadata))
        abbr_tag = xtree.xpath("//abbreviation")[0]
        name = xtree.xpath("//name")[0].text
        abbr_tag.text = overwrite_internal_abbr
        rvmetadata.write_bytes(toxml(xtree))

        # Update BibleData.proPref
        bible_data_entry = '|'.join([folder_id, overwrite_internal_abbr, name, "1"])
        installed_raw = self.read_installed_bibledata()
        installed_raw.append(bible_data_entry)
        pref = root / 'BibleData.proPref'
        new_contents = "InstalledBiblesNew=" + json.dumps(installed_raw) + ';\n'
        pref.write_text(new_contents, encoding='utf-8')

    # ---------- Management operations ----------
    def _load_entries(self) -> List[InstalledBibleEntry]:
        entries: List[InstalledBibleEntry] = []
        for raw in self.read_installed_bibledata():
            meta = self.parse_bible_meta(raw)
            entries.append(InstalledBibleEntry(
                folder_id=meta["id"],
                abbreviation=meta["abbreviation"],
                name=meta["translation"],
                bible_format=meta["bible_format"],
            ))
        return entries

    def _save_entries(self, entries: Iterable[InstalledBibleEntry]) -> None:
        root = self.get_bibles_root_dir()
        if not root:
            raise RuntimeError("Bibles root directory not found")
        pref = root / 'BibleData.proPref'
        raw_list = ["|".join([e.folder_id, e.abbreviation, e.name, e.bible_format]) for e in entries]
        content = "InstalledBiblesNew=" + json.dumps(raw_list) + ';\n'
        pref.write_text(content, encoding='utf-8')

    def list_installed(self) -> List[InstalledBibleEntry]:
        return self._load_entries()

    def delete_installed(self, folder_id: str) -> None:
        root = self.get_bibles_root_dir()
        if not root:
            raise RuntimeError("Bibles root directory not found")
        # remove folder
        target = root / folder_id
        if target.exists() and target.is_dir():
            # remove directory tree
            import shutil as _shutil
            _shutil.rmtree(target)
        # remove entry
        entries = [e for e in self._load_entries() if e.folder_id != folder_id]
        self._save_entries(entries)

    def reassign_abbreviation(self, folder_id: str, new_internal_abbr: str) -> None:
        # ensure not used
        entries = self._load_entries()
        if any(e.abbreviation.lower() == new_internal_abbr.lower() and e.folder_id != folder_id for e in entries):
            raise ValueError(f"Abbreviation already in use: {new_internal_abbr}")

        root = self.get_bibles_root_dir()
        if not root:
            raise RuntimeError("Bibles root directory not found")

        # update rvmetadata.xml
        folder = root / folder_id
        rvmetadata = folder / "rvmetadata.xml"
        if not rvmetadata.is_file():
            raise FileNotFoundError(f"rvmetadata.xml not found for folder {folder_id}")
        xtree = ElementTree.parse(str(rvmetadata))
        abbr_tag = xtree.xpath("//abbreviation")[0]
        abbr_tag.text = new_internal_abbr
        rvmetadata.write_bytes(toxml(xtree))

        # update entry and save
        for e in entries:
            if e.folder_id == folder_id:
                e.abbreviation = new_internal_abbr
                break
        self._save_entries(entries)


class MacInstaller(InstallerBase):
    """Installer implementation for macOS (Darwin)."""

    def get_sideload_dir(self) -> Path:
        return Path('/Library/Application Support/RenewedVision/RVBibles/v2/')


def get_installer() -> InstallerBase:
    """Return an installer appropriate for the current OS."""
    system_str = platform.system()
    if system_str == 'Windows':
        return WindowsInstaller()
    if system_str == 'Darwin':
        return MacInstaller()
    raise RuntimeError("Unsupported operating system for ProPresenter installer")
