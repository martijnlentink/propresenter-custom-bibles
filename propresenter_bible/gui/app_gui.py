"""Simple Tkinter GUI for importing and managing Bibles.

This is an initial GUI to kickstart interactive workflows without the CLI.
It supports:
  - Selecting language and version
  - Downloading and sideloading a Bible
  - Listing/deleting installed Bibles (platform support dependent)
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict

from ..config import DEFAULT_CONFIG
from ..app import BibleImportApp
from ..ui.interface import TkUi
from ..services.api import VersionsItem
from ..progress import ProgressReporter


class DropdownSearch(ttk.Frame):
    """Entry with a dropdown Listbox for filtered search and selection."""

    def __init__(self, master=None, width: int = 40, on_select=None):
        super().__init__(master)
        self._on_select = on_select
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(fill=tk.X, expand=True)
        self._all_values: list[str] = []
        self._filtered: list[str] = []

        # Dropdown toplevel with listbox
        self._drop = tk.Toplevel(self)
        self._drop.withdraw()
        self._drop.overrideredirect(True)
        self._list = tk.Listbox(self._drop, activestyle='dotbox')
        self._list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scroll = ttk.Scrollbar(self._drop, orient='vertical', command=self._list.yview)
        self._list.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bindings
        self.entry.bind('<KeyRelease>', self._on_key)
        self.entry.bind('<Down>', self._entry_down)
        self.entry.bind('<Up>', self._entry_up)
        self.entry.bind('<Return>', lambda e: self._choose())
        self.entry.bind('<Escape>', lambda e: self._hide_drop())
        self.entry.bind('<Button-1>', lambda e: self._show_drop())
        self.entry.bind('<FocusIn>', lambda e: self._show_drop())
        self.entry.bind('<Escape>', lambda e: self._hide_drop())
        self._list.bind('<ButtonRelease-1>', self._choose)
        self._list.bind('<Return>', self._choose)
        self._list.bind('<Up>', self._list_up)
        self._list.bind('<Down>', self._list_down)
        self._list.bind('<Escape>', lambda e: self._hide_drop())

        # Hide when clicking outside
        self.entry.bind('<FocusOut>', self._maybe_hide)
        self._list.bind('<FocusOut>', self._maybe_hide)

    def set_values(self, values: list[str]) -> None:
        self._all_values = list(values)
        self._update_list(self._all_values)

    def set_text(self, text: str) -> None:
        self.var.set(text)

    def get(self) -> str:
        return self.var.get()

    def set_state(self, state: str) -> None:
        try:
            self.entry.configure(state=state)
        except Exception:
            pass

    def _on_key(self, event):
        typed = self.var.get().lower()
        if not typed:
            self._update_list(self._all_values)
            self._show_drop()
            return
        filtered = [v for v in self._all_values if typed in v.lower()]
        self._update_list(filtered)
        self._show_drop()

    def _update_list(self, values: list[str]):
        self._filtered = values
        self._list.delete(0, tk.END)
        for v in values:
            self._list.insert(tk.END, v)
        self._list.configure(height=min(len(values), 10) if values else 1)

    def _place_drop(self):
        try:
            x = self.entry.winfo_rootx()
            y = self.entry.winfo_rooty() + self.entry.winfo_height()
            w = self.entry.winfo_width()
            self._drop.geometry(f"{w}x{self._list.winfo_reqheight()}+{x}+{y}")
        except Exception:
            pass

    def _show_drop(self):
        if not self._filtered:
            self._update_list(self._all_values)
        self._place_drop()
        self._drop.deiconify()
        self._drop.lift()

    def _hide_drop(self):
        self._drop.withdraw()

    def _maybe_hide(self, event=None):
        # hide if focus moved outside both entry and dropdown
        widget = self.focus_get()
        if widget not in (self.entry, self._list):
            self._hide_drop()

    def _choose(self, event=None):
        sel = self._list.curselection()
        if not sel:
            return
        value = self._filtered[sel[0]]
        self.var.set(value)
        self._hide_drop()
        if callable(self._on_select):
            try:
                self._on_select(value)
            except Exception:
                pass

    # Keyboard navigation helpers
    def _entry_down(self, event=None):
        self._show_drop()
        try:
            cur = self._list.curselection()
            idx = (cur[0] + 1) if cur else 0
            self._list.selection_clear(0, tk.END)
            if self._list.size() > 0:
                idx = min(idx, self._list.size() - 1)
                self._list.selection_set(idx)
                self._list.activate(idx)
                self._list.see(idx)
        except Exception:
            pass
        return 'break'

    def _entry_up(self, event=None):
        self._show_drop()
        try:
            cur = self._list.curselection()
            idx = (cur[0] - 1) if cur else 0
            self._list.selection_clear(0, tk.END)
            if self._list.size() > 0:
                idx = max(idx, 0)
                self._list.selection_set(idx)
                self._list.activate(idx)
                self._list.see(idx)
        except Exception:
            pass
        return 'break'

    def _list_down(self, event=None):
        try:
            cur = self._list.curselection()
            idx = (cur[0] + 1) if cur else 0
            self._list.selection_clear(0, tk.END)
            if self._list.size() > 0:
                idx = min(idx, self._list.size() - 1)
                self._list.selection_set(idx)
                self._list.activate(idx)
                self._list.see(idx)
        except Exception:
            pass
        return 'break'

    def _list_up(self, event=None):
        try:
            cur = self._list.curselection()
            idx = (cur[0] - 1) if cur else 0
            self._list.selection_clear(0, tk.END)
            if self._list.size() > 0:
                idx = max(idx, 0)
                self._list.selection_set(idx)
                self._list.activate(idx)
                self._list.see(idx)
        except Exception:
            pass
        return 'break'


class AppGUI:
    def __init__(self) -> None:
        # Create app early so _build_ui can query installer capabilities
        self.app = BibleImportApp(DEFAULT_CONFIG)
        self.root = tk.Tk()
        self.root.title("ProPresenter Bible Manager")
        self._build_ui()
        # Wire GUI UI into app for confirmations and messages
        try:
            self.app.ui = TkUi(self.root, self.status_var)  # type: ignore[attr-defined]
        except Exception:
            pass

        self._lang_map: Dict[str, str] = {}
        self._version_map: Dict[str, VersionsItem] = {}
        self._load_languages()
        self._refresh_installed()

    def _build_ui(self) -> None:
        nb = ttk.Notebook(self.root)
        nb.pack(fill=tk.BOTH, expand=True)

        self.frame_import = ttk.Frame(nb)
        self.frame_manage = ttk.Frame(nb)
        self.frame_propresenter = ttk.Frame(nb)
        nb.add(self.frame_import, text="Import")
        nb.add(self.frame_manage, text="Manage")
        nb.add(self.frame_propresenter, text="ProPresenter")

        # Import tab
        ttk.Label(self.frame_import, text="Language:").grid(row=0, column=0, sticky='w', padx=6, pady=6)
        self.lang_var = tk.StringVar()
        self.lang_input = DropdownSearch(self.frame_import, width=40, on_select=lambda v: self._load_versions())
        self.lang_input.grid(row=0, column=1, sticky='ew', padx=6, pady=6)

        ttk.Label(self.frame_import, text="Version:").grid(row=1, column=0, sticky='w', padx=6, pady=6)
        self.ver_var = tk.StringVar()
        self.ver_input = DropdownSearch(self.frame_import, width=60)
        self.ver_input.grid(row=1, column=1, sticky='ew', padx=6, pady=6)

        # Overwrite options (Windows only)
        self.overwrite_var = tk.BooleanVar(value=False)
        label_text = "Overwrite a ProPresenter Bible (Windows - Recommended)" if self.app.installer.supports_overwrite else "Overwrite a ProPresenter Bible (Windows)"
        self.chk_overwrite = ttk.Checkbutton(self.frame_import, text=label_text, variable=self.overwrite_var, command=self._install_mode_changed)
        self.chk_overwrite.grid(row=2, column=1, sticky='w', padx=6, pady=6)

        self.lbl_overwrite = ttk.Label(self.frame_import, text="Overwrite Target:")
        self.lbl_overwrite.grid(row=3, column=0, sticky='w', padx=6, pady=6)
        self.overwrite_choice_var = tk.StringVar()
        self.overwrite_input = DropdownSearch(self.frame_import, width=60)
        self.overwrite_input.grid(row=3, column=1, sticky='ew', padx=6, pady=6)

        self.btn_download = ttk.Button(self.frame_import, text="Download + Install", command=self._download_install)
        self.btn_download.grid(row=4, column=1, sticky='e', padx=6, pady=12)

        self.frame_import.columnconfigure(1, weight=1)

        # Manage tab (Installed custom bibles)
        self.installed_tree = ttk.Treeview(self.frame_manage, columns=("abbr", "name", "format"), show='headings', height=12)
        self.installed_tree.heading("abbr", text="Abbreviation")
        self.installed_tree.heading("name", text="Name")
        self.installed_tree.heading("format", text="Format")
        self.installed_tree.grid(row=0, column=0, columnspan=3, sticky='nsew', padx=6, pady=6)
        self.frame_manage.rowconfigure(0, weight=1)
        self.frame_manage.columnconfigure(0, weight=1)

        self.btn_refresh = ttk.Button(self.frame_manage, text="Refresh", command=self._refresh_installed)
        self.btn_refresh.grid(row=1, column=0, sticky='w', padx=6, pady=6)

        self.btn_delete = ttk.Button(self.frame_manage, text="Delete Selected", command=self._delete_selected)
        self.btn_delete.grid(row=1, column=2, sticky='e', padx=6, pady=6)
        self.btn_change_abbr = ttk.Button(self.frame_manage, text="Change Abbreviation", command=self._change_abbr_dialog)
        self.btn_change_abbr.grid(row=1, column=1, sticky='e', padx=6, pady=6)

        # ProPresenter tab (Available overwrite bibles)
        self.free_tree = ttk.Treeview(self.frame_propresenter, columns=("language", "name", "display", "internal", "origin", "location"), show='headings', height=14)
        for col, title in (
            ("language", "Language"),
            ("name", "Name"),
            ("display", "Display Abbr"),
            ("internal", "Internal Abbr"),
            ("origin", "Origin"),
            ("location", "Location"),
        ):
            self.free_tree.heading(col, text=title)
            self.free_tree.heading(col, command=lambda c=col: self._sort_tree(self.free_tree, c, False))
        self.free_tree.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=6, pady=6)
        self.frame_propresenter.rowconfigure(0, weight=1)
        self.frame_propresenter.columnconfigure(0, weight=1)
        self.btn_refresh_free = ttk.Button(self.frame_propresenter, text="Refresh", command=self._load_propresenter_tab)
        self.btn_refresh_free.grid(row=1, column=0, sticky='w', padx=6, pady=6)
        self.btn_overwrite_select = ttk.Button(self.frame_propresenter, text="Set Overwrite Target From Selection", command=self._select_overwrite_from_free)
        self.btn_overwrite_select.grid(row=1, column=1, sticky='e', padx=6, pady=6)

        # Status / Progress bar
        self.status_var = tk.StringVar(value="Ready")
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.progress = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self.progress.pack(side=tk.RIGHT, padx=8, pady=4)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor='w')
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=4)

    def _load_languages(self) -> None:
        try:
            langs = self.app.api.get_languages_config()
            # Display label = "local (name)" where they differ
            def label(it):
                return it.local_name if it.local_name == it.name else f"{it.local_name} ({it.name})"
            self._lang_map = {label(x): x.language_tag for x in langs.default_versions}
            self.lang_input.set_values(list(self._lang_map.keys()))
            if self._lang_map:
                # pick first as default
                self.lang_input.set_text(next(iter(self._lang_map.keys())))
                self._load_versions()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load languages: {e}")
        # Load overwrite options and Propresenter overview
        self._load_overwrite_choices()
        self._load_propresenter_tab()
        # Default overwrite on Windows, hide controls on macOS
        if self.app.installer.supports_overwrite:
            self.overwrite_var.set(True)
            self._install_mode_changed()
        else:
            # hide overwrite-related controls
            try:
                self.chk_overwrite.grid_remove()
                self.lbl_overwrite.grid_remove()
                self.overwrite_combo.grid_remove()
            except Exception:
                pass

    def _load_versions(self) -> None:
        try:
            lang_label = self.lang_input.get()
            lang = self._lang_map.get(lang_label)
            if not lang:
                return
            versions = self.app.api.get_versions(lang)
            self._version_map = {f"{v.local_title} ({v.local_abbreviation})": v for v in versions.versions}
            self.ver_input.set_values(list(self._version_map.keys()))
            if self._version_map:
                self.ver_input.set_text(next(iter(self._version_map.keys())))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load versions: {e}")

    def _download_install(self) -> None:
        ver_label = self.ver_input.get()
        version = self._version_map.get(ver_label)
        if not version:
            messagebox.showwarning("Select Version", "Please select a version")
            return

        def worker():
            try:
                metadata = self.app.api.get_version_metadata(version.id)
                # Use the same logic as CLI: download if needed, then build outputs and sideload
                from pathlib import Path
                dl_root = Path(self.app.cfg.download_dir)
                out_root = Path(self.app.cfg.output_dir)
                location = dl_root / version.local_abbreviation
                reporter = GUIProgressReporter(self.root, self.progress, self.status_var)
                self.app._download_if_needed(location, version, metadata, reporter=reporter)
                output_dir = out_root / version.local_abbreviation
                self.app._build_outputs(location, output_dir, metadata, reporter=reporter)
                if self.overwrite_var.get() and self.app.installer.supports_overwrite:
                    target_label = self.overwrite_input.get()
                    target_abbr = self._overwrite_map.get(target_label)
                    if not target_abbr:
                        messagebox.showwarning("Select Overwrite Target", "Please select an overwrite target.")
                        return
                    reporter.start("Overwriting ProPresenter Bible")
                    self.app.installer.overwrite_free_bible(str(output_dir), target_abbr)
                    reporter.done("Overwrite complete")
                    messagebox.showinfo("Done", "Bible downloaded and overwritten. Restart ProPresenter to see changes.")
                else:
                    reporter.start("Sideloading Bible")
                    rvbible_location = self.app._zip_bible_dir(output_dir, version.local_abbreviation)
                    self.app.installer.move_rvbible_propresenter_folder(rvbible_location)
                    reporter.done("Sideload complete")
                    messagebox.showinfo("Done", "Bible downloaded and sideloaded. Restart ProPresenter to see changes.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")
            
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_installed(self) -> None:
        # Clear
        for item in self.installed_tree.get_children():
            self.installed_tree.delete(item)
        try:
            entries = self.app.list_installed()
        except NotImplementedError:
            # Not supported on this platform
            return
        for e in entries:
            self.installed_tree.insert('', 'end', iid=e.folder_id, values=(e.abbreviation, e.name, e.bible_format))

    def _install_mode_changed(self) -> None:
        # Enable/disable overwrite combobox depending on checkbox and platform support
        state = 'normal' if (self.overwrite_var.get() and self.app.installer.supports_overwrite) else 'disabled'
        self.overwrite_input.set_state(state)

    def _load_overwrite_choices(self) -> None:
        # Populate overwrite target choices if supported (Windows)
        self._overwrite_map: Dict[str, str] = {}
        if not self.app.installer.supports_overwrite:
            self._install_mode_changed()
            return
        try:
            choices = self.app.installer.get_available_overwrite_choices()
            labels = []
            for c in choices:
                label = f"{c['language']} - {c['name']} ({c['displayAbbreviation']})"
                self._overwrite_map[label] = c['internalAbbreviation']
                labels.append(label)
            self.overwrite_input.set_values(labels)
            if labels:
                self.overwrite_input.set_text(labels[0])
        finally:
            self._install_mode_changed()

    def _load_propresenter_tab(self) -> None:
        # Show full list of free bibles and whether slot is used
        for item in self.free_tree.get_children():
            self.free_tree.delete(item)
        try:
            free = self.app.installer.load_free_bibles()
            info = {}
            try:
                info = self.app.installer.get_overwrite_info()
            except Exception:
                info = {}
            for fb in free:
                internal = fb["internalAbbreviation"]
                lower = internal.lower()
                meta = info.get(lower, None)
                if meta:
                    origin = meta.get('status', 'Original')
                    loc = meta.get('location', '')
                    display = meta.get('displayAbbreviation') or fb["displayAbbreviation"]
                else:
                    # Free slot
                    origin = 'Free'
                    loc = ''
                    display = fb["displayAbbreviation"]
                self.free_tree.insert('', 'end', iid=internal, values=(fb["language"], fb["name"], display, internal, origin, loc))
        except Exception:
            # silently ignore if not supported
            pass

    def _select_overwrite_from_free(self) -> None:
        # Select an entry from free_tree as overwrite target
        selection = self.free_tree.selection()
        if not selection:
            return
        internal = selection[0]
        # Find matching label
        for label, abbr in self._overwrite_map.items():
            if abbr == internal:
                self.overwrite_var.set(True)
                self._install_mode_changed()
                self.overwrite_choice_var.set(label)
                break

    # ---- Sorting helpers ----
    def _sort_tree(self, tree: ttk.Treeview, col: str, reverse: bool):
        data = [(tree.set(k, col), k) for k in tree.get_children('')]
        try:
            data.sort(key=lambda t: (t[0] is None, t[0]))
        except Exception:
            data.sort(key=lambda t: str(t[0]).lower())
        if reverse:
            data.reverse()
        for index, (_, k) in enumerate(data):
            tree.move(k, '', index)
        tree.heading(col, command=lambda c=col: self._sort_tree(tree, c, not reverse))

    # ---- Manage: Change Abbreviation ----
    def _change_abbr_dialog(self) -> None:
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("Select", "Please select an installed bible")
            return
        folder_id = selection[0]
        dlg = tk.Toplevel(self.root)
        dlg.title("Change Abbreviation")
        ttk.Label(dlg, text=f"For folder: {folder_id}").grid(row=0, column=0, columnspan=2, sticky='w', padx=6, pady=6)
        ttk.Label(dlg, text="New Abbreviation:").grid(row=1, column=0, sticky='w', padx=6, pady=6)
        abbr_var = tk.StringVar()
        dlg.columnconfigure(1, weight=1)
        label_map = {}
        if self.app.installer.supports_overwrite:
            ac = DropdownSearch(dlg, width=40)
            ac.grid(row=1, column=1, sticky='ew', padx=6, pady=6)
            choices = self.app.installer.get_available_overwrite_choices()
            for c in choices:
                # Same labeling as overwrite target: "Language - Name (Display)"
                label = f"{c['language']} - {c['name']} ({c['displayAbbreviation']})"
                label_map[label] = c['internalAbbreviation']
            labels = list(label_map.keys())
            ac.set_values(labels)
            if labels:
                ac.set_text(labels[0])
            get_text = ac.get
        else:
            ent = ttk.Entry(dlg, textvariable=abbr_var, width=40)
            ent.grid(row=1, column=1, sticky='ew', padx=6, pady=6)
            ent.focus_set()
            get_text = lambda: abbr_var.get()

        def on_ok():
            selected_label = get_text().strip()
            new_abbr = label_map.get(selected_label, selected_label)
            if not new_abbr:
                messagebox.showwarning("Input", "Please select a new abbreviation")
                return
            try:
                self.app.reassign_abbreviation(folder_id, new_abbr)
                dlg.destroy()
                self._refresh_installed()
                self._load_propresenter_tab()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")

        ttk.Button(dlg, text="OK", command=on_ok).grid(row=2, column=1, sticky='e', padx=6, pady=6)

    def _delete_selected(self) -> None:
        selection = self.installed_tree.selection()
        if not selection:
            return
        folder_id = selection[0]
        if not messagebox.askyesno("Confirm", f"Delete installed bible {folder_id}? This cannot be undone."):
            return
        try:
            self.app.delete_installed(folder_id)
            self._refresh_installed()
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def run(self) -> None:
        self.root.mainloop()


def run_gui():
    AppGUI().run()
class GUIProgressReporter(ProgressReporter):
    def __init__(self, root: tk.Tk, bar: ttk.Progressbar, status: tk.StringVar):
        self.root = root
        self.bar = bar
        self.status = status
        self._total = None

    def _safe(self, fn, *args, **kwargs):
        self.root.after(0, lambda: fn(*args, **kwargs))

    def start(self, task: str, total: int | None = None) -> None:
        self._total = total
        def _upd():
            self.status.set(task)
            if total and total > 0:
                self.bar.configure(mode='determinate', maximum=total, value=0)
            else:
                self.bar.configure(mode='indeterminate')
                try:
                    self.bar.start(20)
                except Exception:
                    pass
        self._safe(_upd)

    def advance(self, n: int = 1, message: str | None = None) -> None:
        def _upd():
            if message:
                self.status.set(message)
            if str(self.bar.cget('mode')) == 'determinate':
                try:
                    self.bar.step(n)
                except Exception:
                    pass
        self._safe(_upd)

    def set_description(self, message: str) -> None:
        self._safe(lambda: self.status.set(message))

    def done(self, task: str | None = None) -> None:
        def _upd():
            self.bar.configure(value=0)
            if str(self.bar.cget('mode')) == 'indeterminate':
                try:
                    self.bar.stop()
                except Exception:
                    pass
            self.status.set(task or 'Done')
        self._safe(_upd)
