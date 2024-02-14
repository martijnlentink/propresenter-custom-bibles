from os import listdir
from os.path import isfile, join
import json
import xml.etree.ElementTree as ET

mypath = "Chapters"

chapter_files = [f for f in listdir(mypath) if isfile(join(mypath, f))]

for filename in chapter_files:

    with open(join(mypath, filename), "r") as handle:
        json_contents = json.loads(handle.read())
        bible_id = json_contents["data"]["chapter"]["bibleId"]
        book_name = "NBV21"

        book_code = filename[:3]
        chapter = filename.split(".")[-1]

        root = ET.Element('usx', version="2.0")
        book = ET.SubElement(root, 'book', code="2CH", id="")
        chapter = ET.SubElement(root, 'chapter', number=chapter, style="c")
        for el in json_contents["data"]["chapter"]["content"]:
            if el["type"] == "paragraph":
                paragraph = ET.SubElement(root, "para", style="s1")
                for paragraph_col in paragraph["content"]:
                    if paragraph["type"] == "text":
                        paragraph.text = paragraph_col["content"]

            title = ET.SubElement(root, 'para', style="s1")
            title.text = json_contents["data"]["chapter"]


def process_content(elements, xmlnode):
    for el in elements:
        if el["type"] == "paragraph":
            paragraph = ET.SubElement(xmlnode, "para", style=el["style"])
        elif el["type"] == "text":
            ET.SubElement()
            xmlnode.text += paragraph_col["content"]
        elif el["type"] == "verse-number":
            verse = ET.SubElement(xmlnode, "verse", style=el["style"], number=el["content"])
        elif "content" in el:
            process_content(el["content"])

        title = ET.SubElement(root, 'para', style="s1")
        title.text = json_contents["data"]["chapter"]

age = ET.SubElement(person, 'age')