"""Render domain Bible objects into USX XML elements."""

from typing import Optional
from lxml.etree import Element, SubElement
from ..models import Book, Chapter, Paragraph, Verse
from ..parsing.html_to_usx import HtmlToUsxParser


class UsxRenderer:
    def __init__(self, parser: Optional[HtmlToUsxParser] = None):
        # reuse cleanup logic from parser if provided
        self._cleanup = (parser.cleanup_verse_contents if parser else (lambda x: x))

    def render_book(self, book: Book) -> Element:
        usx = Element('usx', version='2.0')
        SubElement(usx, 'book', code=book.code).text = book.code
        for ch in book.chapters:
            self._render_chapter(usx, ch)
        return usx

    def _render_chapter(self, parent: Element, ch: Chapter) -> None:
        SubElement(parent, 'chapter', number=ch.number, style='c')
        for para in ch.paragraphs:
            self._render_paragraph(parent, para)

    def _render_paragraph(self, parent: Element, para: Paragraph) -> None:
        p_el = SubElement(parent, 'para', style=para.style)
        if para.style.startswith('s') and para.text:
            p_el.text = para.text.strip()
            return

        # For verse paragraphs, render a verse tag and put text in tail
        for v in para.verses:
            v_el = SubElement(p_el, 'verse', number=v.number, style='v')
            text = self._cleanup(v.text())
            v_el.tail = text
