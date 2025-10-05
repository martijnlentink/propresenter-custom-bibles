"""UI abstraction for prompts and messages.

Provides a minimal interface so the core app can remain UI-agnostic.
"""

from __future__ import annotations
from typing import List, Protocol, Optional
import threading

try:
    import click
except Exception:  # pragma: no cover
    click = None  # type: ignore


class Ui(Protocol):
    def info(self, message: str) -> None: ...
    def warn(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def confirm(self, message: str) -> bool: ...
    def info_box(self, message: str, title: Optional[str] = None) -> None: ...
    
    # Selection helpers for CLI flows
    def choose_language(self, api_client) -> str: ...
    def select_version(self, versions) -> object: ...
    # Progress and install selection
    def get_progress_reporter(self): ...
    def choose_install_method(self) -> bool: ...  # True = overwrite, False = sideload
    def select_overwrite_choice(self, choices: List[dict]) -> dict: ...
    def prompt_backup_destination(self) -> str: ...


from ..progress import (
    ProgressReporter,
    ConsoleProgressReporter,
    TqdmProgressReporter,
    NullProgressReporter,
)


class ConsoleUi:
    """Console implementation using click for prompts and prints."""

    def info(self, message: str) -> None:
        if click:
            click.echo(message)
        else:
            print(message)

    def warn(self, message: str) -> None:
        self.info(f"[WARN] {message}")

    def error(self, message: str) -> None:
        self.info(f"[ERROR] {message}")

    def confirm(self, message: str) -> bool:
        if click:
            return bool(click.confirm(message))
        return True

    def info_box(self, message: str, title: Optional[str] = None) -> None:
        # In CLI, treat as a normal info line
        self.info(message)

    def choose_language(self, api_client) -> str:
        # use existing helper to offer a nice prompt flow
        from .prompting import choose_language as prompt_choose_language
        return prompt_choose_language(api_client)

    def select_version(self, versions) -> object:
        # versions: List[VersionsItem]
        if not versions:
            raise RuntimeError("No versions available")
        options = {v.id: v for v in versions}
        lines = [f"{v.id}: {v.local_title} ({v.local_abbreviation})" for v in options.values()]
        self.info("\n".join(lines))
        if click:
            selected = click.prompt("Please select the number above to download the scripture", type=int)
        else:
            selected = int(input("Enter version id: "))
        return options[selected]

    # ---- Progress / Install helpers ----
    def get_progress_reporter(self) -> ProgressReporter:
        # CLI prefers tqdm progress bars
        return TqdmProgressReporter()

    def choose_install_method(self) -> bool:
        """Return True for overwrite, False for sideload with inline arrow menu."""
        try:
            from prompt_toolkit.application import Application
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit.layout import Layout
            from prompt_toolkit.layout.controls import FormattedTextControl
            from prompt_toolkit.layout.containers import Window, HSplit
        except Exception:
            return self.confirm("Install using overwrite? (recommended)")

        options = [
            ("Overwrite unused translation (Recommended)", True),
            ("Sideload", False),
        ]
        selected = {"idx": 0}

        def _render_text():
            lines = ["How do you want to install this translation?"]
            for i, (label, _) in enumerate(options):
                box = "☒" if i == selected["idx"] else "☐"
                lines.append(f"{box} {label}")
            return "\n".join(lines)

        control = FormattedTextControl(text=lambda: _render_text())
        root = HSplit([Window(content=control, always_hide_cursor=True)])

        kb = KeyBindings()

        @kb.add('up')
        @kb.add('k')
        def _up(event):  # noqa: ANN001
            selected["idx"] = (selected["idx"] - 1) % len(options)
            event.app.invalidate()

        @kb.add('down')
        @kb.add('j')
        def _down(event):  # noqa: ANN001
            selected["idx"] = (selected["idx"] + 1) % len(options)
            event.app.invalidate()

        @kb.add('enter')
        def _enter(event):  # noqa: ANN001
            event.app.exit(result=options[selected["idx"]][1])

        @kb.add('escape')
        def _esc(event):  # noqa: ANN001
            event.app.exit(result=False)

        app = Application(layout=Layout(root), key_bindings=kb, full_screen=False)
        try:
            return bool(app.run())
        except Exception:
            return self.confirm("Install using overwrite? (recommended)")

    def select_overwrite_choice(self, choices: List[dict]) -> dict:
        """Prompt to select which translation to overwrite from available choices."""
        if not choices:
            raise RuntimeError("No available translations to overwrite")
        try:
            from prompt_toolkit import prompt
            from .prompting import PromptCompleter
        except Exception:
            # Fallback to first choice if prompt toolkit unavailable
            return choices[0]
        prompt_options = {f"{x['language']} - {x['name']}": x["displayAbbreviation"] for x in choices}
        self.info("Which translation would you like to overwrite?")
        self.info("Choose wisely - You will not be able to use this translation anymore!")
        while True:
            choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
            choice_abbr = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower() or x[1].lower() == choice.lower()), None)
            choice_biblemeta = next((x for x in choices if x["displayAbbreviation"].lower() == str(choice_abbr).lower()), None)
            if choice_abbr is not None and choice_biblemeta is not None:
                return choice_biblemeta
            self.warn("Please select one of the abbreviations from the list")

    def prompt_backup_destination(self) -> str:
        # Ask for a destination directory path. No file dialogs, pure CLI.
        if click:
            return click.prompt("Enter backup destination folder", type=str)
        return input("Enter backup destination folder: ")


class TkUi:
    """Tkinter-backed UI for info/warn/error/confirm used by the GUI.

    Note: Selection helpers are not used by the GUI; run_interactive remains
    CLI-only. This class focuses on messaging and confirmation dialogs.
    """

    def __init__(self, root, status_var: Optional[object] = None):
        # root: tk.Tk, status_var: tk.StringVar or compatible (optional)
        self.root = root
        self.status_var = status_var

    def _safe(self, fn, *args, **kwargs):
        try:
            self.root.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            fn(*args, **kwargs)

    def info(self, message: str) -> None:
        if self.status_var is not None:
            def _upd():
                try:
                    self.status_var.set(message)
                except Exception:
                    pass
            self._safe(_upd)

    def warn(self, message: str) -> None:
        try:
            from tkinter import messagebox as mbox
            self._safe(mbox.showwarning, "Warning", message)
        except Exception:
            pass

    def error(self, message: str) -> None:
        try:
            from tkinter import messagebox as mbox
            self._safe(mbox.showerror, "Error", message)
        except Exception:
            pass

    def info_box(self, message: str, title: Optional[str] = None) -> None:
        try:
            from tkinter import messagebox as mbox
            self._safe(mbox.showinfo, title or "Info", message)
        except Exception:
            pass

    def confirm(self, message: str) -> bool:
        try:
            from tkinter import messagebox as mbox
            res = {"value": False}
            evt = threading.Event()

            def _ask():
                try:
                    res["value"] = bool(mbox.askyesno("Confirm", message, parent=self.root))
                except Exception:
                    res["value"] = True
                finally:
                    evt.set()

            # Schedule on the Tk thread and wait for the result
            self._safe(_ask)
            evt.wait()
            return res["value"]
        except Exception:
            # In case GUI is not available, default to True
            return True

    def choose_language(self, api_client) -> str:  # pragma: no cover - not used in GUI
        raise NotImplementedError

    def select_version(self, versions) -> object:  # pragma: no cover - not used in GUI
        raise NotImplementedError

    def get_progress_reporter(self) -> ProgressReporter:
        # For GUI, avoid printing to console by default
        return NullProgressReporter()

    def choose_install_method(self) -> bool:  # pragma: no cover - GUI path likely separate
        # Reuse confirm dialog for a simple choice
        return self.confirm("Install using overwrite? (recommended)")

    def select_overwrite_choice(self, choices: List[dict]) -> dict:  # pragma: no cover - not used in GUI
        raise NotImplementedError

    def prompt_backup_destination(self) -> str:
        try:
            from tkinter import filedialog
            path = filedialog.askdirectory(parent=self.root, title="Choose backup destination")
            if not path:
                raise RuntimeError("No destination chosen")
            return path
        except Exception:
            return ""
