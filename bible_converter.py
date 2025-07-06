import itertools
import os
import re
import string
from typing import Dict

import lxml.html
from lxml import etree as ElementTree
from lxml.etree import Element, SubElement, tostring
from tqdm import tqdm

from config import Config, DEFAULT_CONFIG
from utils import resource_path


class BibleConverter:
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config

    def parse_verse_numbers(self, verse_label: str, verse):
        verse_input = verse_label.strip()

        def extract_verse_from_label(inp: str):
            matches = re.match(r"(?P<verse_int>\d+)(?P<verse_alpha>[a-z])?", inp.strip())
            return (int(matches["verse_int"]), matches["verse_alpha"]) if matches else None

        def extract_verse_from_span(span):
            try:
                return [int(x[1:]) for x in span.classes if re.match(r"v\d+", x)] if span is not None and "verse" in span.classes else None
            except Exception:
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

    def cleanup_verse_contents(self, text: str) -> str:
        a = re.sub(r"([^\S\n])+", r"\1", text)
        a = re.sub(r"([\"'“”‘’«»‹›„‚”’])[^\S\n]+([\"'“”‘’«»‹›„‚”’.,!:;])", r"\1\2", a)
        a = re.sub(r"([.,!:;])[^\S\n]+([.,!:;])", r"\1\2", a)
        a = a.replace("¶", "")
        return a

    def parse_paragraph(self, parent, paragraph, style):
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
            paragraph_el = SubElement(parent, 'para', style=style)
            verse_el = SubElement(paragraph_el, 'verse', number=verse_number_label, style='v')
            verse_number_classes = ' '.join(["v" + str(x).rstrip(string.ascii_lowercase) for x in verse_numbers])
            verse_texts = verse.xpath('//*[@class="verse ' + verse_number_classes + '"]//span[@class="content"]')
            groups = itertools.groupby(verse_texts, lambda x: next(an for an in x.iterancestors() if an.tag == 'div'))
            verse_text = '\n'.join([''.join([x.text_content() for x in group_values]).strip() for parent, group_values in groups])
            verse_el.tail = self.cleanup_verse_contents(verse_text.strip())

    def parse_header(self, parent, headers):
        header_el = SubElement(parent, 'para', style="s1")
        verses = list(itertools.chain(*[header.xpath(".//text()") for header in headers]))
        header_el.text = ''.join(verses).strip()

    def parse_chapter(self, parent, chapter):
        chapter_num = chapter.attrib["data-usfm"].split(".")[-1]
        try:
            chapter_num = str(int(chapter_num))
        except Exception:
            pass
        if chapter_num.isnumeric():
            SubElement(parent, 'chapter', number=chapter_num, style='c')
            for el in chapter:
                heading = el.xpath(".//*[contains(@class,'heading')]")
                if len(heading) > 0:
                    self.parse_header(parent, heading)
                else:
                    self.parse_paragraph(parent, el, "p")
        else:
            print(f"[SKIPPING CHAPTER] Bible chapter has invalid chapter number: {chapter_num}")

    @staticmethod
    def toxml(elem):
        return tostring(elem, encoding='utf-8')

    def process_bible_files(self, location: str, usx_folder: str):
        all_chapters_data: Dict[str, list] = {}
        chapter_files = [f for f in os.listdir(location) if re.match("[A-Z0-9]{3}\.\d+", f)]
        chapter_files.sort(key=lambda x: int(x.split(".")[1]))
        for filename in chapter_files:
            file_location = os.path.join(location, filename)
            with open(file_location, "r", encoding="utf-8") as handle:
                book_code = filename[:3]
                chapter_data = all_chapters_data.get(book_code, [])
                chapter_data.append(handle.read())
                all_chapters_data[book_code] = chapter_data
        iterations = tqdm(all_chapters_data.items(), desc="Chapter")
        for book_code, chapters in iterations:
            iterations.set_description(book_code)
            usx = Element('usx', version='2.0')
            SubElement(usx, 'book', code=book_code).text = book_code
            for chapter in tqdm(chapters, leave=False):
                tree = lxml.html.fromstring(chapter)
                chapter_el = tree.xpath("//*[contains(@class, 'chapter')]")[0]
                self.parse_chapter(usx, chapter_el)
            output_location = os.path.join(usx_folder, book_code + ".usx")
            with open(output_location, 'wb') as file:
                file.write(self.toxml(usx))

    def construct_metadataxmls(self, output_file_loc: str, book_metadata: Dict):
        metadata = resource_path("metadata.xml")
        xml_tree = ElementTree.parse(metadata)
        identification_el = xml_tree.xpath("//identification")[0]
        SubElement(identification_el, "name").text = book_metadata["title"]
        SubElement(identification_el, "nameLocal").text = book_metadata["local_title"]
        SubElement(identification_el, "abbreviation").text = book_metadata["abbreviation"]
        SubElement(identification_el, "abbreviationLocal").text = book_metadata["local_abbreviation"]
        language_el = xml_tree.xpath("//language")[0]
        SubElement(language_el, "iso").text = book_metadata["language"].iso_639_3
        SubElement(language_el, "name").text = book_metadata["language"].name
        SubElement(language_el, "scriptDirection").text = book_metadata["language"].text_direction
        book_names_el = xml_tree.xpath("//bookNames")[0]
        books_el = xml_tree.xpath("//bookList/books")[0]
        unique_short_list = []
        for book in book_metadata["books"]:
            book_code = book.usfm
            short = book.human
            long = book.human_long
            abbr = book.abbreviation
            book_el = SubElement(book_names_el, "book", code=book_code)
            SubElement(book_el, 'long').text = long
            SubElement(book_el, 'short').text = short if short not in unique_short_list else long
            SubElement(book_el, 'abbr').text = abbr
            SubElement(books_el, "book", code=book_code)
            unique_short_list.append(short)
        metadataxml_output = os.path.join(output_file_loc, "metadata.xml")
        with open(metadataxml_output, 'wb') as handle:
            handle.write(self.toxml(xml_tree))
        root = Element("RVBibleMetdata")
        SubElement(root, "name").text = book_metadata["local_title"]
        SubElement(root, "abbreviation").text = book_metadata["abbreviation"]
        SubElement(root, "displayAbbreviation").text = book_metadata["local_abbreviation"]
        SubElement(root, "version").text = "1"
        SubElement(root, "revision").text = "0"
        SubElement(root, "licenseType").text = "0"
        SubElement(root, "license")
        rvmetadataxml_output = os.path.join(output_file_loc, "rvmetadata.xml")
        with open(rvmetadataxml_output, 'wb') as handle:
            handle.write(self.toxml(root))

