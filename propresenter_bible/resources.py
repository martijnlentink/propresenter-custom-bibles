"""Resource helpers for loading templates and serializing XML."""

import os
import sys
from lxml.etree import tostring


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath("Resources")
    return os.path.join(base_path, relative_path)


def toxml(elem) -> bytes:
    """Serialize an lxml Element to bytes (utf-8)."""
    return tostring(elem, encoding="utf-8")
