"""HTML → USX parsing utilities.

Parses YouVersion HTML to domain objects suitable for USX rendering. The
parser also exposes helpers for verse number extraction and text cleanup.
"""

import re
import itertools
import string
from typing import Optional, List
from ..models import Book, Chapter, Paragraph, Verse


class HtmlToUsxParser:
    def cleanup_verse_contents(self, text):
        """Normalize spacing and punctuation quirks in verse text.

        Notes:
        - Collapse extra spaces but keep newlines intact: ``([^\S\n])+`` matches
          any run of whitespace characters that are not a newline.
        - Remove stray spaces around smart quotes and punctuation pairs, e.g.
          "word ” , next" -> "word”, next". The character class includes common
          quote glyphs: “ ” ‘ ’ « » ‹ › „ ‚ etc.
        - Remove spaces between consecutive punctuation marks such as ", ; : ! .".
        - Bible.com historically included the paragraph sign (¶) in some verses
          (see ISA 27:2 NASB2020). We strip that character.
          Example URL: https://www.bible.com/bible/2692/ISA.27.2.NASB2020
        """
        # Remove multiple whitespaces, but do not collapse newlines.
        a = re.sub(r"([^\S\n])+", r"\1", text)
        # Remove spaces around quotes followed/preceded by punctuation.
        a = re.sub(r"([\"'“”‘’«»‹›„‚”’])[^\S\n]+([\"'“”‘’«»‹›„‚”’.,!:;])", r"\1\2", a)
        # Remove spaces between consecutive punctuation marks.
        a = re.sub(r"([.,!:;])[^\S\n]+([.,!:;])", r"\1\2", a)
        # Historically present in some sources – remove paragraph sign.
        a = a.replace('¶', '')
        return a

    def parse_verse_numbers(self, verse_label: str, verse):
        verse_input = verse_label.strip()

        def extract_verse_from_label(inp: str):
            matches = re.match(r"(?P<verse_int>\d+)(?P<verse_alpha>[a-z])?", inp.strip())
            return (int(matches["verse_int"]), matches["verse_alpha"]) if matches else None

        def extract_verse_from_span(span):
            try:
                return [int(x[1:]) for x in span.classes if re.match(r"v\d+", x)] if span is not None and "verse" in span.classes else None
            except:
                return None

        if "-" in verse_input:
            range_numbers = verse_input.split("-", 1)
            lower = extract_verse_from_label(range_numbers[0])
            upper = extract_verse_from_label(range_numbers[-1])
            if isinstance(lower, tuple) and isinstance(upper, tuple):
                ranges = range(lower[0], upper[0])
                return [range_numbers[0], *ranges[1:], range_numbers[-1]]
        elif extract_verse_from_label(verse_input):
            return [verse_input]

        return extract_verse_from_span(verse)

    # Legacy XML-writing methods removed in favor of domain + renderer

    # Domain parsing API
    def parse_header_dom(self, headers) -> Paragraph:
        texts = list(itertools.chain(*[header.xpath(".//text()") for header in headers]))
        p = Paragraph(style="s1")
        p.text = ''.join(texts).strip()
        return p

    def parse_paragraph_dom(self, paragraph, style: str) -> List[Paragraph]:
        results: List[Paragraph] = []
        verses = paragraph.xpath(".//*[contains(@class,'verse')]")
        for verse in verses:
            verse_number_el = verse.xpath('.//span[@class="label"]')
            if len(verse_number_el) == 0:
                continue
            verse_number_label = verse_number_el[0].text
            verse_number_parent = verse_number_el[0].getparent()
            verse_numbers = self.parse_verse_numbers(verse_number_label, verse_number_parent)
            if not verse_numbers:
                continue

            para = Paragraph(style=style)
            v = Verse(number=verse_number_label)

            verse_number_classes = ' '. join(["v" + str(x).rstrip(string.ascii_lowercase) for x in verse_numbers])
            verse_texts = verse.xpath('//*[@class="verse ' + verse_number_classes + '"]//span[@class="content"]')
            groups = itertools.groupby(verse_texts, lambda x: next(an for an in x.iterancestors() if an.tag == 'div'))
            lines = [''.join([x.text_content() for x in group_values]).strip() for parent, group_values in groups]
            cleaned = self.cleanup_verse_contents('\n'.join(lines).strip())
            if cleaned:
                v.add_line(cleaned)
            para.add_verse(v)
            results.append(para)
        return results

    def parse_chapter_dom(self, chapter) -> Optional[Chapter]:
        chapter_num = chapter.attrib["data-usfm"].split(".")[-1]
        try:
            chapter_num = str(int(chapter_num))
        except:
            pass
        if not chapter_num.isnumeric():
            # Skip invalid chapter numbers silently to keep parser UI-agnostic
            return None

        ch = Chapter(number=chapter_num)
        for el in chapter:
            heading = el.xpath(".//*[contains(@class,'heading')]")
            if len(heading) > 0:
                ch.add_paragraph(self.parse_header_dom(heading))
            else:
                for p in self.parse_paragraph_dom(el, "p"):
                    ch.add_paragraph(p)
        return ch
