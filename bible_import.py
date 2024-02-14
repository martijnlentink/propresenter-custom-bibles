import lxml.html
from os import listdir
from xml.dom import minidom
import regex as re
from lxml import etree as ElementTree
from lxml.etree import Element, SubElement, tostring
import os
from uuid import uuid4
import platform
import datetime
import shutil
from requests import get
import time
import html
import json

headers = {
    "Referer": "https://bible.com/",
    "Origin": "https://bible.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

download_folder = "download"
output_folder = "output"
resources_loc = "Resources"

def retrieve_bibles_for_language(lang):
    bibles_resp = get(f"https://www.bible.com/api/bible/versions?language_tag={lang}&type=all", headers=headers)
    bible_list_json = bibles_resp.json()
    available_bibles = { x['id']:x for x in bible_list_json["response"]["data"]["versions"]}

    return available_bibles

def retrieve_api_id():
    landing_page_response = get("https://www.bible.com")
    html_page = lxml.html.fromstring(landing_page_response.text)
    next_data_script = html_page.xpath("//script[@id='__NEXT_DATA__']")
    next_data = json.loads(next_data_script[0].text)
    api_id = next_data["buildId"]

    return api_id

def download_bible_chapters(location, selected_bible_id, selected_bible_abbr):
    next = "GEN.1"
    retries = 5
    book_names = {}
    api_id = retrieve_api_id()

    while next is not None:
        try:
            print(f"Retrieving bible chapter: {next}".ljust(40), end="\r", flush=True)

            res = get(f"https://www.bible.com/_next/data/{api_id}/en/bible/{selected_bible_id}/{next}.{selected_bible_abbr}.json", headers=headers)
            data = res.json()
            filename = data["pageProps"]["params"]["usfm"]
            contents = data["pageProps"]["chapterInfo"]["content"]

            human_book_name: str = data['pageProps']['chapterInfo']["reference"]["human"]
            book_code = next[:3]
            book_names[book_code] = human_book_name.rsplit(' ', 1)[0]

            os.makedirs(location, exist_ok=True)

            with open(os.path.join(location, filename), "w", encoding='utf-8') as file:
                file.writelines(html.unescape(contents))

            nextObj = data["pageProps"]["chapterInfo"]["next"]
            next = nextObj["usfm"][0] if nextObj is not None else None

            time.sleep(.5)
        except:
            retries -= 1
            if retries > 0:
                time.sleep(5)
            else:
                raise

def parse_chapter(parent, chapter):
    chapter_num = list(chapter.classes)[-1][2:]
    SubElement(parent, 'chapter', number=chapter_num, style='c')

    for el in chapter:
        if "s1" in el.classes or "c1" in el.classes:
            parse_header(parent, el)
        elif "p" in el.classes or "q" in el.classes:
            parse_paragraph(parent, el, "p")

def parse_paragraph(parent, paragraph, style):
    verses = paragraph.xpath(".//*[contains(@class,'verse')]")
    for verse in verses:
        verse_number_el = verse.xpath('.//span[@class="label"]')
        if len(verse_number_el) == 0:
            continue

        verse_number = verse_number_el[0].text
        paragraph_el = SubElement(parent, 'para', style=style)
        verse_el = SubElement(paragraph_el, 'verse', number=verse_number, style='v')

        verse_texts = verse.xpath('//*[@class="verse v' + verse_number + '"]/span[@class="content"]/text()')
        verse_el.tail = ' '.join([x.strip() for x in verse_texts])

def parse_header(parent, header):
    header_el = SubElement(parent, 'para', style="s1")

    verses = header.xpath(".//text()")
    header_el.text = ''.join(verses)

def pretty_print_xml(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.childNodes[0].toprettyxml(indent="  ")

def process_bible_files(location, usx_folder):
    all_chapters_data = {}
    chapter_files = [f for f in listdir(location) if re.match("[A-Z0-9]{3}\.\d+", f)]
    for filename in chapter_files:
        file_location = os.path.join(location, filename)

        with open(file_location, "r", encoding='utf-8') as handle:
            book_code = filename[:3]

            chapter_data = all_chapters_data.get(book_code, [])
            chapter_data.append(handle.read())
            all_chapters_data[book_code] = chapter_data

    for book_code, chapters in all_chapters_data.items():
        # Create the root element
        usx = Element('usx', version='2.0')
        SubElement(usx, 'book', code=book_code).text = book_code

        for chapter in chapters:
            tree = lxml.html.fromstring(chapter)
            chapter_el = tree.xpath("//*[contains(@class, 'chapter')]")[0]
            parse_chapter(usx, chapter_el)

        output_location = os.path.join(usx_folder, book_code + ".usx")
        # Writing to USX file
        with open(output_location, 'w', encoding='utf-8') as file:
            file.write(pretty_print_xml(usx))

def construct_metadataxmls(file_loc, output_file_loc, book_id):
    book_metadata_resp = get(f"https://www.bible.com/api/bible/version/{book_id}")
    js = book_metadata_resp.json()

    metadata = os.path.join(file_loc, "metadata.xml")
    xml_tree = ElementTree.parse(metadata)

    identification_el = xml_tree.xpath("//identification")[0]
    SubElement(identification_el, "name").text = js["title"]
    SubElement(identification_el, "nameLocal").text = js["local_title"]
    SubElement(identification_el, "abbreviation").text = js["abbreviation"]
    SubElement(identification_el, "abbreviationLocal").text = js["local_abbreviation"]

    language_el = xml_tree.xpath("//language")[0]
    SubElement(language_el, "iso").text = js["language"]['iso_639_3']
    SubElement(language_el, "name").text = js["language"]['name']
    SubElement(language_el, "scriptDirection").text = js["language"]['text_direction']

    book_names_el = xml_tree.xpath("//bookNames")[0]
    books_el = xml_tree.xpath("//bookList/books")[0]

    for book in js["books"]:
        book_code = book['usfm']
        canon = book['canon']
        short = book['human']
        long = book['human_long']
        abbr = book['abbreviation']
        book_el = SubElement(book_names_el, "book", code=book_code)
        SubElement(book_el, 'long').text = long
        SubElement(book_el, 'short').text = short
        SubElement(book_el, 'abbr').text = abbr

        SubElement(books_el, "book", code=book_code)

    metadataxml_output = os.path.join(output_file_loc, "metadata.xml")
    with open(metadataxml_output, 'w', encoding='utf-8') as handle:
        handle.write(pretty_print_xml(xml_tree))

    root = Element("RVBibleMetdata")
    SubElement(root, "name").text = js["local_title"]
    SubElement(root, "abbreviation").text = js["abbreviation"]
    SubElement(root, "displayAbbreviation").text = js["local_abbreviation"]
    SubElement(root, "version").text = "1"
    SubElement(root, "revision").text = "0"
    SubElement(root, "licenseType").text = "0"
    SubElement(root, "license")

    rvmetadataxml_output = os.path.join(output_file_loc, "rvmetadata.xml")
    with open(rvmetadataxml_output, 'w', encoding='utf-8') as handle:
        handle.write(pretty_print_xml(root))

def move_rvbible_propresenter_folder(rvbible_loc):
    system_str = platform.system()
    _, filename = os.path.split(rvbible_loc)

    if system_str == 'Windows':
        program_data = os.getenv('PROGRAMDATA')
        propresenter_bible_location = os.path.join(program_data, 'RenewedVision\ProPresenter\Bibles\sideload')
        os.makedirs(propresenter_bible_location, exist_ok=True)
    elif system_str == 'Darwin':
        propresenter_bible_location = '/Library/Application Support/RenewedVision/RVBibles/v2/'
    else:
        raise Exception("Unable to determine operating system, please copy the bible manually")

    new_file_loc = os.path.join(propresenter_bible_location, filename)
    shutil.copyfile(rvbible_loc, new_file_loc)


if __name__ == '__main__':
    os.makedirs(download_folder, exist_ok=True)

    language = input("Which language would you want to download? - Please give in a valid ISO 639 three character language code\n")
    available_bibles = retrieve_bibles_for_language(language)
    options_response_str = '\n'.join([f"{x['id']}: {x['local_title']} ({x['local_abbreviation']})" for x in available_bibles.values()])

    print(options_response_str)

    selected_bible_id = int(input("Please select the number above to download the scripture\n"))
    selected_bible = available_bibles[selected_bible_id]
    selected_bible_abbeviation = selected_bible['local_abbreviation']

    print(f"Starting download {selected_bible['local_title']}")

    # perform bible download
    location = os.path.join(download_folder, selected_bible_abbeviation)
    download_bible_chapters(location, selected_bible_id, selected_bible_abbeviation)

    output_folder = os.path.join(output_folder, selected_bible_abbeviation)
    usx_folder = os.path.join(output_folder, "USX_1")
    os.makedirs(usx_folder)

    # process downloaded bible files to ProPresenter RVBible format
    process_bible_files(location, usx_folder)
    construct_metadataxmls(resources_loc, output_folder, selected_bible_id)

    # create zip of bible files
    zip_location = os.path.join(output_folder, f"../{selected_bible_abbeviation}.rvbible")
    shutil.make_archive(zip_location, 'zip', output_folder)
    rvbible_location = shutil.move(zip_location + ".zip", zip_location)

    print("Moving bible to ProPresenter directory")

    move_rvbible_propresenter_folder(rvbible_location)