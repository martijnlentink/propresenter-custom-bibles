"""Configuration for the importer application and services."""

from dataclasses import dataclass
from typing import Dict


DEFAULT_HEADERS: Dict[str, str] = {
    "Referer": "https://bible.com/",
    "Origin": "https://bible.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
}


@dataclass
class Config:
    """Top-level configuration for HTTP headers and I/O folders."""

    headers: Dict[str, str]
    download_dir: str
    output_dir: str


DEFAULT_CONFIG = Config(
    headers=DEFAULT_HEADERS,
    download_dir="download",
    output_dir="output",
)
