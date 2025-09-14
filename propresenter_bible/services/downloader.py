"""Download Bible content from bible.com to a local folder.

This module provides `BibleDownloader` which orchestrates either offline zip
downloads (Yves) or online per-chapter fetching. It is UI-agnostic and uses a
`ProgressReporter` abstraction for progress updates.
"""

import io
import os
import html
import time
import zipfile
import pathlib
from requests import get
from typing import Optional
from ..services.api import BibleApiClient, VersionMetadata, ChapterPage
from ..services.decoder import YvesDecoder
from ..progress import ProgressReporter, NullProgressReporter


class BibleDownloader:
    """Download orchestrator for Bible content.

    - Uses `BibleApiClient` for network calls.
    - Uses `YvesDecoder` for offline zip decoding.
    - Reports progress through `ProgressReporter`.
    """

    def __init__(self, api: BibleApiClient, decoder: YvesDecoder):
        self._api = api
        self._decoder = decoder

    def download(
        self,
        location: str,
        version_id: int,
        abbr: str,
        version_meta: VersionMetadata,
        reporter: Optional[ProgressReporter] = None,
    ) -> None:
        reporter = reporter or NullProgressReporter()
        offline = version_meta.offline
        if offline:
            offline_url = offline.url
            response = get(f"https:{offline_url}")
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
            yves_zip = os.path.join(location, "yves")
            zip_file.extractall(yves_zip)

            files = list(pathlib.Path(yves_zip).rglob("*.yves"))
            reporter.start("Decode Yves files to HTML", total=len(files))
            for yves_chapter_file in files:
                decoded_data = self._decoder.read_file(str(yves_chapter_file))
                chapter_name = yves_chapter_file.parent.name
                chapter_num = yves_chapter_file.name.split(".")[0]
                chapter_identifier = f"{chapter_name}.{chapter_num}"
                with open(os.path.join(location, chapter_identifier), "w", encoding='utf-8') as file:
                    file.writelines(decoded_data)
                reporter.advance(1, message=str(yves_chapter_file.name))
            reporter.done("Decode Yves files to HTML")
            return

        # Online per-page download
        next_usfm = version_meta["books"][0]["chapters"][0]["usfm"]
        retries = 5
        build_id = self._api.get_build_id()

        reporter.start("Retrieve bible chapters")
        while next_usfm is not None:
            try:
                reporter.set_description(f"Retrieving {next_usfm}")
                page: ChapterPage = self._api.get_chapter_page(build_id, version_id, next_usfm, abbr)
                filename = page.pageProps.params.usfm
                contents = page.pageProps.chapterInfo.content
                with open(os.path.join(location, filename), "w", encoding='utf-8') as file:
                    file.writelines(html.unescape(contents))
                next_obj = page.pageProps.chapterInfo.next
                next_usfm = next_obj.usfm[0] if next_obj is not None and next_obj.usfm else None
                reporter.advance(1, message=filename)
            except Exception:
                retries -= 1
                if retries > 0:
                    time.sleep(5)
                else:
                    raise
        reporter.done("Retrieve bible chapters")
