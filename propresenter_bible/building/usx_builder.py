"""Build USX files from downloaded chapter HTML using domain models.

This builder is UI-agnostic; it reports progress through the ProgressReporter
interface.
"""

import os
import re
from os import listdir
import lxml.html
from ..parsing.html_to_usx import HtmlToUsxParser
from ..models import Book
from .usx_renderer import UsxRenderer
from typing import Optional, Dict
from ..progress import ProgressReporter, NullProgressReporter


class UsxBuilder:
    def __init__(self, parser: HtmlToUsxParser):
        self._parser = parser
        self._renderer = UsxRenderer(parser)

    def build_from_downloads(
        self,
        location,
        usx_folder,
        book_names: Optional[Dict[str, str]] = None,
        reporter: Optional[ProgressReporter] = None,
    ):
        reporter = reporter or NullProgressReporter()
        all_chapters_data = {}
        chapter_files = [f for f in listdir(location) if re.match("[A-Z0-9]{3}\.\d+", f)]
        chapter_files.sort(key=lambda x: int(x.split(".")[1]))

        for filename in chapter_files:
            file_location = os.path.join(location, filename)
            with open(file_location, "r", encoding='utf-8') as handle:
                book_code = filename[:3]
                chapter_data = all_chapters_data.get(book_code, [])
                chapter_data.append(handle.read())
                all_chapters_data[book_code] = chapter_data

        for book_code, chapters in all_chapters_data.items():
            reporter.start(f"Build USX for {book_code}", total=len(chapters))
            name = (book_names or {}).get(book_code) if book_names else None
            book = Book(code=book_code, name=name)
            for chapter_html in chapters:
                tree = lxml.html.fromstring(chapter_html)
                chapter_el = tree.xpath("//*[contains(@class, 'chapter')]")[0]
                chapter_dom = self._parser.parse_chapter_dom(chapter_el)
                if chapter_dom is not None:
                    book.add_chapter(chapter_dom)
                reporter.advance(1)
            usx = self._renderer.render_book(book)
            output_location = os.path.join(usx_folder, book_code + ".usx")
            from ..resources import toxml
            with open(output_location, 'wb') as file:
                file.write(toxml(usx))
            reporter.done(f"Build USX for {book_code}")
