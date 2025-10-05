"""Progress reporting abstractions.

This module defines lightweight, UI-agnostic progress reporter interfaces for
core library code to emit progress updates without directly depending on any
UI or console libraries. The application layer can implement these interfaces
to display progress (e.g., with print statements, tqdm, GUI progress bars).
"""

from __future__ import annotations
from typing import Optional


class ProgressReporter:
    """Interface for reporting progress.

    Implementations should be side-effect free for non-UI contexts.
    """

    def start(self, task: str, total: Optional[int] = None) -> None:
        """Announce a new task with an optional total work count."""
        pass

    def advance(self, n: int = 1, message: Optional[str] = None) -> None:
        """Advance the current task by n, optionally updating a message."""
        pass

    def set_description(self, message: str) -> None:
        """Set or update the description of the current task."""
        pass

    def done(self, task: Optional[str] = None) -> None:
        """Mark the current or given task as completed."""
        pass


class NullProgressReporter(ProgressReporter):
    """No-op progress reporter for headless or test environments."""

    def start(self, task: str, total: Optional[int] = None) -> None:
        return

    def advance(self, n: int = 1, message: Optional[str] = None) -> None:
        return

    def set_description(self, message: str) -> None:
        return

    def done(self, task: Optional[str] = None) -> None:
        return


class ConsoleProgressReporter(ProgressReporter):
    """Simple console reporter using print statements.

    Keeps the core logic UI-agnostic while still providing feedback when used
    from a CLI application.
    """

    def __init__(self) -> None:
        self._current_task: Optional[str] = None
        self._total: Optional[int] = None
        self._count: int = 0

    def start(self, task: str, total: Optional[int] = None) -> None:
        self._current_task = task
        self._total = total
        self._count = 0
        print(f"[START] {task}" + (f" total={total}" if total is not None else ""))

    def advance(self, n: int = 1, message: Optional[str] = None) -> None:
        self._count += n
        if message:
            print(f"[PROGRESS] {self._current_task}: {message}")
        elif self._total is not None:
            print(f"[PROGRESS] {self._current_task}: {self._count}/{self._total}")

    def set_description(self, message: str) -> None:
        print(f"[DESC] {message}")

    def done(self, task: Optional[str] = None) -> None:
        return


class TqdmProgressReporter(ProgressReporter):
    """tqdm-based progress reporter for CLI usage.

    Creates a new tqdm bar per task started. Safe to use with code that
    sequentially calls start/done multiple times.
    """

    def __init__(self) -> None:
        self._bar = None
        self._current_task: Optional[str] = None

    def start(self, task: str, total: Optional[int] = None) -> None:
        try:
            from tqdm import tqdm  # type: ignore
        except Exception:
            # Fallback to simple console reporter if tqdm is unavailable
            self._fallback = ConsoleProgressReporter()
            self._fallback.start(task, total)
            return
        self._fallback = None  # type: ignore[attr-defined]
        self._current_task = task
        # Replace any existing bar (clear previous line). Using leave=False ensures
        # we don't accumulate multiple bars on screen.
        if getattr(self, "_bar", None) is not None:
            try:
                self._bar.close()
            except Exception:
                pass
            finally:
                self._bar = None
        desc = task
        self._bar = tqdm(total=total, desc=desc, unit="it", leave=False, dynamic_ncols=True)

    def advance(self, n: int = 1, message: Optional[str] = None) -> None:
        if getattr(self, "_fallback", None) is not None:
            self._fallback.advance(n, message)  # type: ignore[attr-defined]
            return
        if self._bar is not None:
            if message:
                try:
                    self._bar.set_postfix_str(str(message), refresh=False)
                except Exception:
                    pass
            try:
                self._bar.update(n)
            except Exception:
                pass

    def set_description(self, message: str) -> None:
        if getattr(self, "_fallback", None) is not None:
            self._fallback.set_description(message)  # type: ignore[attr-defined]
            return
        if self._bar is not None:
            try:
                # Prepend task for clarity when nested
                self._bar.set_description_str(message)
            except Exception:
                pass

    def done(self, task: Optional[str] = None) -> None:
        if getattr(self, "_fallback", None) is not None:
            self._fallback.done(task)  # type: ignore[attr-defined]
            return
        if self._bar is not None:
            try:
                self._bar.close()
            except Exception:
                pass
            finally:
                self._bar = None

