import lxml.html
from os import listdir
import re
from lxml import etree as ElementTree
from lxml.etree import Element, SubElement, tostring
import os
import sys
from uuid import uuid4
import platform
import datetime
import shutil
from requests import get
import time
import html
import json
import click
import itertools
from tqdm import tqdm

headers = {
    "Referer": "https://bible.com/",
    "Origin": "https://bible.com",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
}

download_folder = "download"
output_folder = "output"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath("Resources")

    return os.path.join(base_path, relative_path)

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

def download_bible_chapters(location, selected_bible_id, selected_bible_abbr, bible_metadata):
    next = bible_metadata["books"][0]["chapters"][0]["usfm"]
    retries = 5
    book_names = {}
    api_id = retrieve_api_id()

    while next is not None:
        try:
            print(f"Retrieving bible chapter: {next}".ljust(40), end="\r", flush=True)

            url = f"https://www.bible.com/_next/data/{api_id}/en/bible/{selected_bible_id}/{next}.{selected_bible_abbr}.json"
            res = get(url, headers=headers)
            data = res.json()

            if "__N_REDIRECT" in data["pageProps"] or data["pageProps"]["chapterInfo"] is None:
                res = get(f"{url}?version={selected_bible_id}&usfm={next}.{selected_bible_abbr}")
                data = res.json()

            filename = data["pageProps"]["params"]["usfm"]
            contents = data["pageProps"]["chapterInfo"]["content"]

            human_book_name: str = data['pageProps']['chapterInfo']["reference"]["human"]
            book_code = next[:3]
            book_names[book_code] = human_book_name.rsplit(' ', 1)[0]

            with open(os.path.join(location, filename), "w", encoding='utf-8') as file:
                file.writelines(html.unescape(contents))

            nextObj = data["pageProps"]["chapterInfo"]["next"]
            next = nextObj["usfm"][0] if nextObj is not None else None

            #time.sleep(.5)
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
        heading = el.xpath(".//*[contains(@class,'heading')]")
        if len(heading) > 0:
            parse_header(parent, heading)
        else:
            parse_paragraph(parent, el, "p")

def parse_paragraph(parent, paragraph, style):
    verses = paragraph.xpath(".//*[contains(@class,'verse')]")
    for verse in verses:
        verse_number_el = verse.xpath('.//span[@class="label"]')
        if len(verse_number_el) == 0:
            continue

        verse_number = verse_number_el[0].text

        if not verse_number.isdecimal():
            continue

        paragraph_el = SubElement(parent, 'para', style=style)
        verse_el = SubElement(paragraph_el, 'verse', number=verse_number, style='v')

        # retrieve all verse text components
        verse_texts = verse.xpath('//*[@class="verse v' + verse_number + '"]//span[@class="content"]')
        # group by div-tag, these will be text blocks for a single line
        groups = itertools.groupby(verse_texts, lambda x: next(an for an in x.iterancestors() if an.tag == 'div'))
        # trim all texts and omit whitespace texts, then join them by a line separator
        verse_text = '\n'.join([''.join([x.text_content() for x in group_values]).strip() for parent, group_values in groups])
        # make sure that space do not occur in between punctuation
        verse_el.tail = remove_unnecessary_whitespaces(verse_text.strip())
        # remove paragraph marks
        verse_el.tail = remove_paragraph_marks(verse_el.tail)

def parse_header(parent, headers):
    header_el = SubElement(parent, 'para', style="s1")

    verses = list(itertools.chain(*[header.xpath(".//text()") for header in headers]))
    header_el.text = ''.join(verses).strip()

def toxml(elem):
    """Return a XML string for the Element."""
    return tostring(elem, encoding='utf-8')

def process_bible_files(location, usx_folder):
    all_chapters_data = {}
    # find valid chapter files
    chapter_files = [f for f in listdir(location) if re.match("[A-Z0-9]{3}\.\d+", f)]
    # sort chapters numerically, for OSX users
    chapter_files.sort(key=lambda x: int(x.split(".")[1]))

    for filename in chapter_files:
        file_location = os.path.join(location, filename)

        with open(file_location, "r", encoding='utf-8') as handle:
            book_code = filename[:3]

            chapter_data = all_chapters_data.get(book_code, [])
            chapter_data.append(handle.read())
            all_chapters_data[book_code] = chapter_data

    iterations = tqdm(all_chapters_data.items(), desc="Chapter")
    for book_code, chapters in iterations:
        iterations.set_description(book_code)
        # Create the root element
        usx = Element('usx', version='2.0')
        SubElement(usx, 'book', code=book_code).text = book_code

        for chapter in tqdm(chapters, leave=False):
            tree = lxml.html.fromstring(chapter)
            chapter_el = tree.xpath("//*[contains(@class, 'chapter')]")[0]
            parse_chapter(usx, chapter_el)

        output_location = os.path.join(usx_folder, book_code + ".usx")
        # Writing to USX file
        with open(output_location, 'wb') as file:
            file.write(toxml(usx))

def retrieve_bible_metadata(book_id):
    book_metadata_resp = get(f"https://www.bible.com/api/bible/version/{book_id}")
    return book_metadata_resp.json()

def construct_metadataxmls(output_file_loc, book_metadata):
    metadata = resource_path("metadata.xml")
    xml_tree = ElementTree.parse(metadata)

    identification_el = xml_tree.xpath("//identification")[0]
    SubElement(identification_el, "name").text = book_metadata["title"]
    SubElement(identification_el, "nameLocal").text = book_metadata["local_title"]
    SubElement(identification_el, "abbreviation").text = book_metadata["abbreviation"]
    SubElement(identification_el, "abbreviationLocal").text = book_metadata["local_abbreviation"]

    language_el = xml_tree.xpath("//language")[0]
    SubElement(language_el, "iso").text = book_metadata["language"]['iso_639_3']
    SubElement(language_el, "name").text = book_metadata["language"]['name']
    SubElement(language_el, "scriptDirection").text = book_metadata["language"]['text_direction']

    book_names_el = xml_tree.xpath("//bookNames")[0]
    books_el = xml_tree.xpath("//bookList/books")[0]

    for book in book_metadata["books"]:
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
    with open(metadataxml_output, 'wb') as handle:
        handle.write(toxml(xml_tree))

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
        handle.write(toxml(root))

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

def remove_unnecessary_whitespaces(text):
    # Remove multiple whitespaces, don't consider new lines
    a = re.sub(r"([^\S\n])+", r"\1", text)
    # Remove spaces in between specific punctuation sequences
    a = re.sub(r"([\"'“”‘’«»‹›„‚”’])[^\S\n]+([\"'“”‘’«»‹›„‚”’.,!:;])", r"\1\2", a)
    a = re.sub(r"([.,!:;])[^\S\n]+([.,!:;])", r"\1\2", a)
    return a

def remove_paragraph_marks(text):
    # Replace paragraph marks with an empty string
    a = re.compile(r'¶')
    a = re.sub(a, '', text)
    return a

if __name__ == '__main__':
    os.makedirs(download_folder, exist_ok=True)

    click.echo("Which language would you want to download?")
    language = click.prompt("Please give in a valid ISO 639 three character language code")
    available_bibles = retrieve_bibles_for_language(language)
    options_response_str = '\n'.join([f"{x['id']}: {x['local_title']} ({x['local_abbreviation']})" for x in available_bibles.values()])

    print(options_response_str)

    selected_bible_id = click.prompt("Please select the number above to download the scripture", type=int)
    selected_bible = available_bibles[selected_bible_id]
    selected_bible_abbeviation = selected_bible['local_abbreviation']

    print("Retrieve bible metadata")
    bible_metadata = retrieve_bible_metadata(selected_bible_id)

    # perform bible download
    location = os.path.join(download_folder, selected_bible_abbeviation)
    download_required = not os.path.exists(location) or click.confirm(f"It appears that there is already a download folder for bible {selected_bible_abbeviation}. Are you sure you want to download the bible contents?")
    
    if download_required:
        os.makedirs(location, exist_ok=True)

        print(f"Starting download {selected_bible['local_title']}")
        download_bible_chapters(location, selected_bible_id, selected_bible_abbeviation, bible_metadata)

    output_folder = os.path.join(output_folder, selected_bible_abbeviation)
    usx_folder = os.path.join(output_folder, "USX_1")
    os.makedirs(usx_folder, exist_ok=True)

    # process downloaded bible files to ProPresenter RVBible format
    print("Converting chapters to valid USX format")
    process_bible_files(location, usx_folder)
    construct_metadataxmls(output_folder, bible_metadata)

    # create zip of bible files
    zip_location = os.path.join(output_folder, f"../{selected_bible_abbeviation}.rvbible")
    shutil.make_archive(zip_location, 'zip', output_folder)
    rvbible_location = shutil.move(zip_location + ".zip", zip_location)

    print("Moving bible to ProPresenter directory")

    move_rvbible_propresenter_folder(rvbible_location)

    print("Done! Please restart ProPresenter and check if the bible is correctly installed.")
    input("Press enter to close...")