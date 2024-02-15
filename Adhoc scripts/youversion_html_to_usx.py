import lxml.html
from os import listdir
from os.path import isfile
from xml.dom import minidom
import regex as re
from xml.etree.ElementTree import Element, SubElement, tostring

def parse_chapter(parent, chapter):
    chapter_num = list(chapter.classes)[-1][2:]
    SubElement(parent, 'chapter', number=chapter_num, style='c')

    for el in chapter:
        if "s1" in el.classes:
            parse_header(parent, el)
        elif "p" in el.classes:
            parse_paragraph(parent, el, "p")

def parse_paragraph(parent, paragraph, style):
    paragraphEl = SubElement(parent, 'para', style=style)

    verses = paragraph.xpath(".//*[contains(@class,'verse')]")
    for verse in verses:
        verse_number_el = verse.xpath('.//span[@class="label"]')
        if len(verse_number_el) == 0:
            continue

        verse_number = verse_number_el[0].text
        verseEl = SubElement(paragraphEl, 'verse', number=verse_number, style='v')

        verse_texts = verse.xpath('.//span[@class="content"]/text()')
        verseEl.tail = ''.join(verse_texts)

def parse_header(parent, header):
    headerEl = SubElement(parent, 'para', style="s1")

    verses = header.xpath(".//text()")
    headerEl.text = ''.join(verses)

def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.childNodes[0].toprettyxml(indent="  ")

all_chapters_data = {}
chapter_files = [f for f in listdir() if isfile(f) and re.match("[A-Z0-9]{3}\.\d+", f)]
for filename in chapter_files:

    with open(filename, "r", encoding='utf-8') as handle:
        book_code = filename[:3]

        chapter_data = all_chapters_data.get(book_code, [])
        chapter_data.append(handle.read())
        all_chapters_data[book_code] = chapter_data

for book_code, chapters in all_chapters_data.items():
    # Create the root element
    usx = Element('usx', version='2.0')
    book = SubElement(usx, 'book', code=book_code)

    for chapter in chapters:
        tree = lxml.html.fromstring(chapter)

        chapterEl = tree.xpath("//*[contains(@class, 'chapter')]")[0]
        chapterUsfm = chapterEl.attrib['data-usfm']

        parse_chapter(book, chapterEl)

    # Writing to USX file
    with open(book_code + ".usx", 'w', encoding='utf-8') as file:
        file.write(prettify(usx))



