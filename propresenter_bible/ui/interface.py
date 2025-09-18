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
    
    # Selection helpers for CLI flows
    def choose_language(self, api_client) -> str: ...
    def select_version(self, versions) -> object: ...


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
