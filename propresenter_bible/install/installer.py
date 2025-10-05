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
    def get_sideload_dirs(self) -> List[Path]:
        """Return possible sideload directories in preference order.

        The first existing path should be treated as the preferred location.
        If none exist, callers may use the first candidate as the default.
        """
        raise NotImplementedError

    def get_primary_sideload_dir(self) -> Path:
        """Return the primary sideload directory to write to.

        Chooses the first existing directory from `get_sideload_dirs()`; if none
        exist, returns the first candidate. Raises if there are no candidates.
        """
        candidates = self.get_sideload_dirs()
        if not candidates:
            raise RuntimeError("No sideload directory candidates available for this platform")
        for c in candidates:
            if c.exists():
                return c
        return candidates[0]

    def get_backup_items(self) -> List[tuple[str, Path]]:
        """Return a list of (label, path) items to back up.

        Labels are used as destination subfolders. Implementations should return
        the minimal set of locations that represent the current Bible state for
        the platform (e.g., a single root on Windows, sideload dirs on macOS).
        """
        raise NotImplementedError

    def get_restore_targets(self) -> List[tuple[str, Path]]:
        """Return a list of (label, destination_path) that can be restored to.

        Labels must correspond to those produced by get_backup_items().
        """
        raise NotImplementedError

    def get_bibles_root_dir(self) -> Optional[Path]:
        """Root dir where BibleData.proPref lives (if applicable to the OS)."""
        return None

    def move_rvbible_propresenter_folder(self, rvbible_loc: str) -> None:
        dest_dir = self.get_primary_sideload_dir()
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

    def get_overwrite_info(self) -> dict:
        """Return mapping of internal abbr (lowercase) to info dict with keys:
        - status: 'Overridden' | 'Original'
        - location: path string
        - displayAbbreviation: optional display abbr
        Only meaningful on platforms that support overwrite; default empty.
        """
        return {}

    def plan_dangling_cleanup(self) -> dict:
        """Return a plan describing dangling installs to remove.

        Should return a dict with keys:
          - folder_ids: list[str]
          - total_size: int (bytes)

        Platforms that do not support this should raise NotImplementedError.
        """
        raise NotImplementedError("Dangling cleanup is not supported on this platform")


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

    def get_sideload_dirs(self) -> List[Path]:
        root = self.get_bibles_root_dir()
        return [root / 'sideload'] if root else []

    def get_bibles_root_dir(self) -> Optional[Path]:
        import os as _os
        base = _os.getenv('PROGRAMDATA')
        return Path(base) / 'RenewedVision' / 'ProPresenter' / 'Bibles' if base else None

    def get_backup_items(self) -> List[tuple[str, Path]]:
        root = self.get_bibles_root_dir()
        return [('Bibles', root)] if root else []

    def get_restore_targets(self) -> List[tuple[str, Path]]:
        root = self.get_bibles_root_dir()
        return [('Bibles', root)] if root else []

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

    # ---------- Dangling cleanup (Windows only) ----------
    def _dir_size(self, path: Path) -> int:
        total = 0
        try:
            for p in path.rglob('*'):
                if p.is_file():
                    try:
                        total += p.stat().st_size
                    except Exception:
                        pass
        except Exception:
            pass
        return total

    def plan_dangling_cleanup(self) -> dict:
        """Return a plan for cleaning dangling installs.

        A "dangling" install is an installed entry whose abbreviation matches the
        name of an .rvbible file present in the sideload directory.

        Returns a dict with keys:
          - folder_ids: list[str]
          - total_size: int (bytes)
        """
        root = self.get_bibles_root_dir()
        if not root:
            return {"folder_ids": [], "total_size": 0}
        # Collect sideload abbreviations from filenames
        sideload_abbrs = set()
        for d in self.get_sideload_dirs():
            if not d or not d.exists():
                continue
            for f in d.glob('*.rvbible'):
                try:
                    sideload_abbrs.add(f.stem.lower())
                except Exception:
                    pass
        if not sideload_abbrs:
            return {"folder_ids": [], "total_size": 0}

        # Match against installed entries
        candidates: List[str] = []
        for e in self._load_entries():
            try:
                if e.name.lower() in sideload_abbrs:
                    candidates.append(e.folder_id)
            except Exception:
                pass

        # Compute total size for those folders
        total_size = 0
        for fid in candidates:
            p = root / fid
            if p.exists() and p.is_dir():
                total_size += self._dir_size(p)
        return {"folder_ids": candidates, "total_size": total_size}

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

    def get_overwrite_info(self) -> dict:
        info = {}
        root = self.get_bibles_root_dir()
        if not root:
            return info
        try:
            installed_raw = self.read_installed_bibledata()
            for raw in installed_raw:
                meta = self.parse_bible_meta(raw)
                folder = root / meta["id"]
                # Determine rightsHolderAbbreviation
                rights = None
                installed_name = None
                try:
                    mpath = folder / 'metadata.xml'
                    if mpath.is_file():
                        xt = ElementTree.parse(str(mpath))
                        node = xt.xpath('//DBLMetadata/contact/rightsHolderAbbreviation')
                        rights = node[0].text if node else None
                        # Try to get installed name (prefer local name if you want)
                        n = xt.xpath('//identification/name')
                        if n:
                            installed_name = n[0].text
                        else:
                            nloc = xt.xpath('//identification/nameLocal')
                            installed_name = nloc[0].text if nloc else None
                except Exception:
                    rights = None
                # displayAbbreviation from rvmetadata.xml
                display = None
                try:
                    rv = folder / 'rvmetadata.xml'
                    if rv.is_file():
                        xt = ElementTree.parse(str(rv))
                        node = xt.xpath('//displayAbbreviation')
                        display = node[0].text if node else None
                except Exception:
                    display = None
                status = 'Overridden' if rights == 'NBV21' else 'Original'
                info[meta["abbreviation"].lower()] = {
                    'status': status,
                    'location': str(folder),
                    'displayAbbreviation': display,
                    'name': installed_name,
                }
        except Exception:
            return info
        return info


class MacInstaller(InstallerBase):
    """Installer implementation for macOS (Darwin)."""

    def get_sideload_dirs(self) -> List[Path]:
        # Prefer new per-user path, then legacy system path
        rel = Path('Library') / 'Application Support' / 'RenewedVision' / 'RVBibles' / 'v2'
        user_path = Path.home() / rel
        system_path = Path('/') / rel
        return [user_path, system_path]

    def get_backup_items(self) -> List[tuple[str, Path]]:
        items: List[tuple[str, Path]] = []
        for p in self.get_sideload_dirs():
            if not p.exists():
                continue
            label = 'RVBibles_user' if str(p).startswith(str(Path.home())) else 'RVBibles_system'
            items.append((label, p))
        return items

    def get_restore_targets(self) -> List[tuple[str, Path]]:
        rel = Path('Library') / 'Application Support' / 'RenewedVision' / 'RVBibles' / 'v2'
        user_path = Path.home() / rel
        system_path = Path('/') / rel
        return [('RVBibles_user', user_path), ('RVBibles_system', system_path)]

    # On macOS, ProPresenter consumes .rvbible files placed in the sideload dir.
    # There is no BibleData.proPref to mutate, so management is file-based.

    def list_installed(self) -> List[InstalledBibleEntry]:
        results: List[InstalledBibleEntry] = []
        seen: set[str] = set()
        for sideload in self.get_sideload_dirs():
            if not sideload.exists():
                continue
            for f in sideload.glob('*.rvbible'):
                key = f.stem.lower()
                if key in seen:
                    continue
                seen.add(key)
                results.append(InstalledBibleEntry(
                    folder_id=f.stem,  # using filename stem as identifier
                    abbreviation=f.stem,
                    name=f.stem,
                    bible_format='rvbible',
                ))
        return results

    def delete_installed(self, folder_id: str) -> None:
        # Search all candidate sideload directories
        for sideload in self.get_sideload_dirs():
            # Accept both exact stem and full filename
            candidate = sideload / f"{folder_id}.rvbible"
            if candidate.exists():
                candidate.unlink()
                return
            raw = sideload / folder_id
            if raw.exists():
                raw.unlink()
                return
        raise FileNotFoundError(f"No installed bible found with id or filename '{folder_id}'")

    def reassign_abbreviation(self, folder_id: str, new_internal_abbr: str) -> None:
        """On macOS, adjust displayAbbreviation inside the .rvbible archive.

        This does not enforce uniqueness; ProPresenter supports arbitrary values.
        """
        import zipfile
        # locate the file across all candidate sideload directories
        zip_path: Optional[Path] = None
        for sideload in self.get_sideload_dirs():
            candidate = sideload / f"{folder_id}.rvbible"
            if candidate.exists():
                zip_path = candidate
                break
            raw = sideload / folder_id
            if raw.exists():
                zip_path = raw
                break
        if not zip_path:
            raise FileNotFoundError(f"Sideload file not found: {folder_id}")

        tmp_path = zip_path.with_suffix('.tmp')
        with zipfile.ZipFile(zip_path, 'r') as zin, zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
            replaced = False
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith('rvmetadata.xml'):
                    try:
                        xt = ElementTree.fromstring(data)
                        node = xt.xpath('//displayAbbreviation')
                        if node:
                            node[0].text = new_internal_abbr
                            data = toxml(xt)
                            replaced = True
                    except Exception:
                        pass
                zout.writestr(item, data)
            if not replaced:
                raise RuntimeError('rvmetadata.xml not found inside rvbible')
        # replace original
        zip_path.unlink()
        tmp_path.rename(zip_path)

    def get_overwrite_info(self) -> dict:
        """Return status/location/displayAbbreviation for sideloaded files on macOS."""
        import zipfile
        info: dict = {}
        for sideload in self.get_sideload_dirs():
            if not sideload.exists():
                continue
            for f in sideload.glob('*.rvbible'):
                rights = None
                display = None
                installed_name = None
                try:
                    with zipfile.ZipFile(f, 'r') as zf:
                        # metadata.xml
                        try:
                            with zf.open('metadata.xml') as m:
                                xt = ElementTree.parse(m)
                                node = xt.xpath('//DBLMetadata/contact/rightsHolderAbbreviation')
                                rights = node[0].text if node else None
                                nn = xt.xpath('//identification/name')
                                if nn:
                                    installed_name = nn[0].text
                                else:
                                    nnl = xt.xpath('//identification/nameLocal')
                                    installed_name = nnl[0].text if nnl else None
                        except Exception:
                            rights = None
                        # rvmetadata.xml
                        try:
                            with zf.open('rvmetadata.xml') as rm:
                                xt = ElementTree.parse(rm)
                                node = xt.xpath('//displayAbbreviation')
                                display = node[0].text if node else None
                        except Exception:
                            display = None
                except Exception:
                    pass
                status = 'Overridden' if rights == 'NBV21' else 'Original'
                key = f.stem.lower()
                info[key] = {'status': status, 'location': str(f), 'displayAbbreviation': display, 'name': installed_name}
        return info


def get_installer() -> InstallerBase:
    """Return an installer appropriate for the current OS."""
    system_str = platform.system()
    if system_str == 'Windows':
        return WindowsInstaller()
    if system_str == 'Darwin':
        return MacInstaller()
    raise RuntimeError("Unsupported operating system for ProPresenter installer")
