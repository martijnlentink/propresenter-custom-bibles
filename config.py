from dataclasses import dataclass
from typing import Dict

@dataclass
class Config:
    headers: Dict[str, str]
    download_folder: str = "download"
    output_folder: str = "output"

DEFAULT_CONFIG = Config(
    headers={
        "Referer": "https://bible.com/",
        "Origin": "https://bible.com",
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        ),
    }
)
