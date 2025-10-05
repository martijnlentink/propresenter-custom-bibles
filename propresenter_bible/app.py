"""Application orchestration (UI-bound).

This module wires the core library components together and manages user
interaction. It passes a ProgressReporter to the core layers but does not
handle progress display logic within the core modules.
"""

import shutil
import os
from .config import Config
from .services.api import BibleApiClient, VersionsResponse, VersionMetadata, VersionsItem
from .services.decoder import YvesDecoder
from .services.downloader import BibleDownloader
from .parsing.html_to_usx import HtmlToUsxParser
from .building.usx_builder import UsxBuilder
from .metadata.builder import MetadataBuilder
from .install.installer import get_installer, InstallerBase
from .ui.interface import Ui, ConsoleUi
from pathlib import Path


class BibleImportApp:
    def __init__(self, cfg: Config, ui: Ui | None = None):
        """Initialize the app with configuration and core services."""
        self.cfg = cfg
        self.api = BibleApiClient(cfg)
        self.decoder = YvesDecoder()
        self.downloader = BibleDownloader(self.api, self.decoder)
        self.parser = HtmlToUsxParser()
        self.usx = UsxBuilder(self.parser)
        self.meta = MetadataBuilder()
        self.installer: InstallerBase = get_installer()
        self.ui: Ui = ui or ConsoleUi()

    def run_interactive(self) -> None:
        """Run an interactive CLI workflow to import and install a Bible."""
        download_root = Path(self.cfg.download_dir)
        download_root.mkdir(parents=True, exist_ok=True)

        language = self._prompt_language()
        selected = self._prompt_version(language)
        metadata = self.api.get_version_metadata(selected.id)

        location = download_root / selected.local_abbreviation
        self._download_if_needed(location, selected, metadata)

        output_dir = Path(self.cfg.output_dir) / selected.local_abbreviation
        self._build_outputs(location, output_dir, metadata)
        self._install(output_dir, selected.local_abbreviation)

        print("Done! Please restart ProPresenter and check if the bible is correctly installed.")
        input("Press enter to close...")

    def _prompt_language(self) -> str:
        self.ui.info("Which language would you want to download?")
        return self.ui.choose_language(self.api)

    def _prompt_version(self, language: str) -> VersionsItem:
        versions: VersionsResponse = self.api.get_versions(language)
        by_id = {v.id: v for v in versions.versions}
        return self.ui.select_version(list(by_id.values()))

    def _download_if_needed(self, location: Path, version: VersionsItem, metadata: VersionMetadata, reporter=None) -> None:
        need_download = True if not location.exists() else self.ui.confirm(
            f"It appears that there is already a download folder for bible {version.local_abbreviation}.\nAre you sure you want to download the bible contents instead of using cache?"
        )
        if not need_download:
            return
        self.ui.info(f"Starting download {version.local_title}")
        location.mkdir(parents=True, exist_ok=True)
        # Ask UI for the appropriate progress reporter
        rep = reporter or self.ui.get_progress_reporter()
        self.downloader.download(str(location), version.id, version.local_abbreviation, metadata, reporter=rep)

    def _build_outputs(self, location: Path, output_dir: Path, metadata: VersionMetadata, reporter=None) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.ui.info("Converting chapters to valid USX format")
        book_names = {b.usfm: b.human for b in metadata.books}
        rep = reporter or self.ui.get_progress_reporter()
        usx_out = output_dir / "USX_1"
        usx_out.mkdir(parents=True, exist_ok=True)
        self.usx.build_from_downloads(str(location), str(usx_out), book_names=book_names, reporter=rep)
        self.meta.build(str(output_dir), metadata)

    def _zip_bible_dir(self, output_dir: Path, abbr: str) -> str:
        zip_base = output_dir.parent / f"{abbr}.rvbible"
        shutil.make_archive(str(zip_base), 'zip', str(output_dir))
        return shutil.move(str(zip_base) + ".zip", str(zip_base))

    def _install(self, output_dir: Path, abbr: str) -> None:
        if self.installer.supports_overwrite:
            # Delegate choice to UI
            use_overwrite = self.ui.choose_install_method()
            if use_overwrite:
                # Interactive overwrite selection in UI layer
                choices = self.installer.get_available_overwrite_choices()
                choice_biblemeta = self.ui.select_overwrite_choice(choices)
                self.installer.overwrite_free_bible(str(output_dir), choice_biblemeta["internalAbbreviation"])  # type: ignore[index]
                return

        rvbible_location = self._zip_bible_dir(output_dir, abbr)
        self.ui.info("Moving bible to ProPresenter directory")
        self.installer.move_rvbible_propresenter_folder(rvbible_location)

    # ---- Management (non-interactive) ----
    def list_installed(self):
        return self.installer.list_installed()

    def delete_installed(self, folder_id: str) -> None:
        self.installer.delete_installed(folder_id)

    def reassign_abbreviation(self, folder_id: str, new_internal_abbr: str) -> None:
        self.installer.reassign_abbreviation(folder_id, new_internal_abbr)

    # No additional UI helpers in this class; UI interactions are delegated

    # ---- Backup (CLI-driven) ----
    def backup(self, dest: str | None = None) -> None:
        """Backup current Bible state to a user-provided destination folder.

        - Windows: copies entire Bibles root directory
        - macOS: copies existing sideload directories
        """
        from datetime import datetime
        base_dest = Path(dest) if dest else Path(self.ui.prompt_backup_destination())
        base_dest.mkdir(parents=True, exist_ok=True)

        items = self.installer.get_backup_items()
        if not items:
            self.ui.error("No ProPresenter Bible locations found to back up.")
            return

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_root = base_dest / f"ProPresenter-Bibles-Backup-{timestamp}"
        backup_root.mkdir(parents=True, exist_ok=True)

        for label, src in items:
            target = backup_root / label
            if target.exists():
                # Ensure a unique target
                i = 1
                while (backup_root / f"{label}-{i}").exists():
                    i += 1
                target = backup_root / f"{label}-{i}"
            # Copy tree
            try:
                shutil.copytree(src, target)
            except Exception as e:
                self.ui.warn(f"Failed to back up {src}: {e}")

        self.ui.info(f"Backup completed to: {backup_root}")

    def restore(self, src: str, overwrite: bool = False) -> None:
        """Restore a previously backed up state from the given folder.

        Expects `src` to be a folder that contains labeled subfolders created by
        `backup()` (e.g., 'Bibles', 'RVBibles_user').
        """
        src_path = Path(src)
        if not src_path.exists() or not src_path.is_dir():
            raise FileNotFoundError(f"Backup folder not found: {src}")

        # Build label->dest map for this platform
        targets = {label: dest for label, dest in self.installer.get_restore_targets()}
        if not targets:
            self.ui.error("No valid restore targets for this platform.")
            return

        # Iterate subfolders in src and restore to matching targets
        import shutil as _shutil
        restored_any = False
        for child in src_path.iterdir():
            if not child.is_dir():
                continue
            dest = targets.get(child.name)
            if not dest:
                # Skip unknown folder labels
                continue
            dest.mkdir(parents=True, exist_ok=True)
            try:
                # Merge copy. If overwrite is False, existing files are preserved.
                # Perform a manual merge to control overwrite behavior.
                for root, dirs, files in os.walk(child):
                    rel = Path(root).relative_to(child)
                    target_dir = dest / rel
                    target_dir.mkdir(parents=True, exist_ok=True)
                    for d in dirs:
                        (target_dir / d).mkdir(parents=True, exist_ok=True)
                    for f in files:
                        src_file = Path(root) / f
                        dst_file = target_dir / f
                        if dst_file.exists() and not overwrite:
                            continue
                        _shutil.copy2(src_file, dst_file)
                restored_any = True
            except Exception as e:
                self.ui.warn(f"Failed to restore {child.name}: {e}")

        if not restored_any:
            self.ui.warn("No matching backup content was restored.")
        else:
            self.ui.info("Restore completed.")

    # ---- Cleanup dangling installs (Windows) ----
    def cleanup_dangling(self) -> None:
        """Detect and remove dangling installed bibles on Windows.

        A dangling install is an installed entry whose abbreviation matches a
        .rvbible present in the sideload directory.
        """
        try:
            info = self.installer.plan_dangling_cleanup()
        except NotImplementedError:
            self.ui.warn("Dangling cleanup is not supported on this platform.")
            return
        folder_ids = info.get('folder_ids', [])
        total_size = int(info.get('total_size', 0))
        if not folder_ids:
            self.ui.info_box("No dangling installations found.", title="Cleanup")
            return

        def _fmt_bytes(n: int) -> str:
            units = ['B', 'KB', 'MB', 'GB', 'TB']
            size = float(n)
            for u in units:
                if size < 1024.0 or u == units[-1]:
                    return f"{size:.1f} {u}"
                size /= 1024.0
            return f"{n} B"

        msg = (
            f"Found {len(folder_ids)} dangling installation(s), "
            f"reclaiming approximately {_fmt_bytes(total_size)}.\nProceed to delete?"
        )
        if not self.ui.confirm(msg):
            return
        for fid in folder_ids:
            try:
                self.installer.delete_installed(fid)
            except Exception as e:
                self.ui.warn(f"Failed to delete {fid}: {e}")
        self.ui.info("Dangling cleanup complete.")
