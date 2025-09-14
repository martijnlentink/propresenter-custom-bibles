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
        print(f"[DONE] {task or self._current_task}")

