from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from os import listdir
from os.path import isfile
import html
import json

chapter_files = [f for f in listdir() if isfile(f)]

def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.childNodes[0].toprettyxml(indent="  ")

def run(currentContent, xmlElement):
    if isinstance(currentContent, str):
        currentContent = html.escape(currentContent)

        if len(xmlElement) == 0:
            xmlElement.text = currentContent if xmlElement.text == None else xmlElement.text + currentContent
        else:
             target = list(xmlElement.iter())[-1]
             target.tail = currentContent if target.tail == None else target.tail + currentContent
    elif isinstance(currentContent, list):
        for el in currentContent:
            run(el, xmlElement)
    else:
        if currentContent["type"] == "verse-number":
            xmlElement = SubElement(xmlElement, 'verse', number=currentContent['content'], style=currentContent['style'])
        elif currentContent["type"] == "paragraph":
            xmlElement = SubElement(xmlElement, 'para', style=currentContent["style"])

        if "content" in currentContent:
            run(currentContent["content"], xmlElement)


def create_usx_from_chapters_with_titles(chapters_data, book_code):
    # Create the root element
    usx = Element('usx', version='2.0')

    for chapter_data in chapters_data:
        # Add book element if it's the first chapter
        if chapter_data['data']['chapter']['id'].split('.')[1] == '1':
            book_code = chapter_data['data']['chapter']['bookId']
            book = SubElement(usx, 'book', code=book_code, id='854adbc07178b15f')
            book.text = book_code

        # Add chapter element
        chapter_num = chapter_data['data']['chapter']['id'].split('.')[1]
        chapter = SubElement(usx, 'chapter', number=chapter_num, style='c')

        # Iterate through the content and add verses and titles
        for content in chapter_data['data']['chapter']['content']:
            run(content, usx)

     # Writing to USX file
    with open(book_code + ".usx", 'w', encoding='utf-8') as file:
        file.write(prettify(usx))


all_chapters_data = {}
for filename in chapter_files:

    with open(filename, "r", encoding='utf-8') as handle:
        book_code = filename[:3]

        chapter_data = all_chapters_data.get(book_code, [])
        chapter_data.append(json.loads(handle.read()))
        all_chapters_data[book_code] = chapter_data

for book_code, all_chapters_data in all_chapters_data.items():
    # Convert chapters to USX with dynamic titles
    usx_content_with_titles = create_usx_from_chapters_with_titles(all_chapters_data, book_code)
