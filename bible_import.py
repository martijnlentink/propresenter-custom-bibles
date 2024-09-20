from typing import Dict
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
import zipfile
import io
import pathlib
import string
from tqdm import tqdm
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.shortcuts import radiolist_dialog

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

def read_yves_file(file_name):
	with open(file_name, 'rb') as handle:
		arrayOfByte = handle.read()
		return decode_yves_bytes(arrayOfByte)

# adaptation of the app Java code youversion.bible.reader.api.impl.ChapterContentData.decode
def decode_yves_bytes(input_bytes):
    i2 = len(input_bytes)
    bArr = bytearray(input_bytes)
    for i3 in range(0, i2, 2):
        i4 = i3 + 1
        if i2 > i4:
            temp_i4 = ((bArr[i3] & 255) >> 5) | ((bArr[i3] & 255) << 3)
            bArr[i3] = ((bArr[i4] & 255) >> 5) | ((bArr[i4] & 255) << 3) & 0xFF
            bArr[i4] = temp_i4 & 0xFF
        else:
            bArr[i3] = (((bArr[i3] & 255) >> 5) | ((bArr[i3] & 255) << 3)) & 0xFF

    # Convert the modified bytearray back to bytes for decoding
    str_output = bytes(bArr).decode("UTF-8", errors="ignore")
    return str_output

class PromptCompleter(Completer):

    def __init__(self, options: Dict[str, str]):
        self._options = options

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor()
        for display_text, value in self._options.items():
            if word_before_cursor.lower() in display_text.lower():
                yield Completion(display_text, start_position=-len(word_before_cursor), display_meta=value)


def choose_language():

    languages = get("https://www.bible.com/api/bible/configuration")
    langs = languages.json()
    lang_versions = langs["response"]["data"]["default_versions"]

    def gen_name(lang_version):
        local_name = lang_version["local_name"]
        name = lang_version["name"]
        return local_name if local_name == name else f"{local_name} ({name})"

    prompt_options = {gen_name(x): x["iso_639_3"] for x in lang_versions }

    print("Choose the language you want to retrieve")
    while True:
        choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
        lang_code = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower()), None)
        if lang_code is not None:
            return lang_code

        print("Please select a valid language from the list. Press TAB to select.")

def retrieve_api_id():
    landing_page_response = get("https://www.bible.com")
    html_page = lxml.html.fromstring(landing_page_response.text)
    next_data_script = html_page.xpath("//script[@id='__NEXT_DATA__']")
    next_data = json.loads(next_data_script[0].text)
    api_id = next_data["buildId"]

    return api_id

def download_bible_chapters(location, selected_bible_id, selected_bible_abbr, bible_metadata):
    offline_location = bible_metadata.get("offline", None)

    # Download bible using offline yves files
    if offline_location is not None:
        offline_url = offline_location["url"]
        response = get(f"https:{offline_url}")
        zip_file = zipfile.ZipFile(io.BytesIO(response.content))
        yves_zip = os.path.join(location, "yves")
        zip_file.extractall(yves_zip)

        for yves_chapter_file in tqdm(pathlib.Path(yves_zip).rglob("*.yves"), desc="Decode Yves files to HTML"):
            decoded_data = read_yves_file(yves_chapter_file)
            chapter_name = yves_chapter_file.parent.name
            chapter_num = yves_chapter_file.name.split(".")[0]

            chapter_identifier = f"{chapter_name}.{chapter_num}"
            with open(os.path.join(location, chapter_identifier), "w", encoding='utf-8') as file:
                file.writelines(decoded_data)
    else:
        #  Download bible per page
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
    chapter_num = chapter.attrib["data-usfm"].split(".")[-1]
    SubElement(parent, 'chapter', number=chapter_num, style='c')

    for el in chapter:
        heading = el.xpath(".//*[contains(@class,'heading')]")
        if len(heading) > 0:
            parse_header(parent, heading)
        else:
            parse_paragraph(parent, el, "p")

def parse_verse_numbers(verse_label: str, verse):
    verse_input = verse_label.strip()

    def extract_verse_from_label(inp: str):
        matches = re.match(r"(?P<verse_int>\d+)(?P<verse_alpha>[a-z])?", inp.strip())
        return (int(matches["verse_int"]), matches["verse_alpha"]) if matches else None
    
    def extract_verse_from_span(span):
        try:
            # matches based on class names like 'v1 v2 v3' etc.
            return [int(x[1:]) for x in span.classes if re.match(r"v\d+", x)] if span is not None and "verse" in span.classes else None
        except:
            return None

    # in the exceptional translations where verses are returned in ranges
    if "-" in verse_input:
        range_numbers = verse_input.split("-", 1)

        lower = extract_verse_from_label(range_numbers[0])
        upper = extract_verse_from_label(range_numbers[-1])

        # ensures that ranges require an upper and lower bound
        if isinstance(lower, tuple) and isinstance(upper, tuple):
            ranges = range(lower[0], upper[0])
            return [range_numbers[0], *ranges[1:], range_numbers[-1]]
    # single verse
    elif extract_verse_from_label(verse_input):
        return [verse_input]

    # if label based matching fails, try it using the span classes
    # fixes bug #15 - Related to the fact that UKR Bible 1755 in ECC5.19 the label is displayed as - (dash) https://www.bible.com/bible/1755/ECC.5
    return extract_verse_from_span(verse)

def parse_paragraph(parent, paragraph, style):
    verses = paragraph.xpath(".//*[contains(@class,'verse')]")
    for verse in verses:
        verse_number_el = verse.xpath('.//span[@class="label"]')
        if len(verse_number_el) == 0:
            continue

        verse_number_label = verse_number_el[0].text
        verse_number_parent = verse_number_el[0].getparent()
        verse_numbers = parse_verse_numbers(verse_number_label, verse_number_parent)

        if not verse_numbers:
            continue

        paragraph_el = SubElement(parent, 'para', style=style)
        verse_el = SubElement(paragraph_el, 'verse', number=verse_number_label, style='v')

        # retrieve all verse text components - strip alphanumeric suffix
        verse_number_classes = ' '. join(["v" + str(x).rstrip(string.ascii_lowercase) for x in verse_numbers])
        verse_texts = verse.xpath('//*[@class="verse ' + verse_number_classes + '"]//span[@class="content"]')
        # group by div-tag, these will be text blocks for a single line
        groups = itertools.groupby(verse_texts, lambda x: next(an for an in x.iterancestors() if an.tag == 'div'))
        # trim all texts and omit whitespace texts, then join them by a line separator
        verse_text = '\n'.join([''.join([x.text_content() for x in group_values]).strip() for parent, group_values in groups])
        # verse contents post-processing
        verse_el.tail = cleanup_verse_contents(verse_text.strip())

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
    book_metadata_resp = get(f"https://nodejs.bible.com/api/bible/version/3.3?id={book_id}")
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

def cleanup_verse_contents(text):
    # Remove multiple whitespaces, don't consider new lines
    a = re.sub(r"([^\S\n])+", r"\1", text)
    # Remove spaces in between specific punctuation sequences
    a = re.sub(r"([\"'“”‘’«»‹›„‚”’])[^\S\n]+([\"'“”‘’«»‹›„‚”’.,!:;])", r"\1\2", a)
    a = re.sub(r"([.,!:;])[^\S\n]+([.,!:;])", r"\1\2", a)

    # Fixes issue #4 - Bible.com mistakenly contains paragraph characters
    # Specifically at this verse: https://www.bible.com/bible/2692/ISA.27.2.NASB2020
    # consider deletion if source is updated
    a = a.replace('¶', '')
    return a

def overwrite_free_bible(bible_folder):
    program_data = os.getenv('PROGRAMDATA')
    def parse_bible_meta(bible_meta_string):
        splitted = bible_meta_string.split('|')
        return { "id": splitted[0], "abbreviation": splitted[1], "translation": splitted[2], "bible_format": splitted[3] }
    
    with open(resource_path("available_bibles.json"), "r", encoding='utf-8') as free_bibles:
        free_bibles_txt = free_bibles.read()
        free_bibles_json = json.loads(free_bibles_txt)

    propresenter_bible_location = os.path.join(program_data, 'RenewedVision\ProPresenter\Bibles')
    bible_data_propref_loc = os.path.join(propresenter_bible_location, "BibleData.proPref")

    bibledata_json = []
    bible_metadatas = []
    if os.path.isfile(bible_data_propref_loc):
        with open(bible_data_propref_loc, "r", encoding='utf-8') as bibledata_handle:
            try:
                # reading and parsing of BibleData.proPref - on Windows this stores the bible locations in the folder
                bibledata_contents = bibledata_handle.read()
                bibledata_arr_text = re.match(r"InstalledBiblesNew=(?P<array>\[[^\]]*?]);?", bibledata_contents)
                bibledata_json: list = json.loads(bibledata_arr_text.group("array"))
                bible_metadatas = [parse_bible_meta(x) for x in bibledata_json]
            except:
                pass

        # determine which abbreviations are in use to give them back
        used_abbreviations = set(x["abbreviation"] for x in bible_metadatas)
        prompt_options = {f'{x["language"]} - {x["name"]}': x["displayAbbreviation"] for x in free_bibles_json if x["internalAbbreviation"] not in used_abbreviations}
        print("Which translation would you like to overwrite?")
        print("Choose wisely - Please mind that you will not be able to use this translation anymore!")

        while True:
           choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
           choice_abbr = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower() or x[1].lower() == choice.lower()), None)
           choice_biblemeta = next((x for x in free_bibles_json if x["displayAbbreviation"].lower() == str(choice_abbr).lower()), None)
           if choice_abbr is not None and choice_biblemeta is not None:
               break

           print("Please select one of the abbreviations from the list")

        overwrite_abbr = choice_biblemeta["internalAbbreviation"]

        # 1. Generate a new folder to store the bible in
        folder_id = str(uuid4())
        new_bible_folder = os.path.join(propresenter_bible_location, folder_id)
        shutil.move(bible_folder, new_bible_folder)

        # 2. Adjust metadata such that the abbreviation matches the one we are to overwrite
        rvmetadata = os.path.join(new_bible_folder, "rvmetadata.xml")
        xtree = ElementTree.parse(rvmetadata)
        abbr_tag = xtree.xpath("//abbreviation")[0]
        name = xtree.xpath("//name")[0].text
        abbr_tag.text = overwrite_abbr

        with open(rvmetadata, 'wb') as rvmetadata_handle:
            rvmetadata_handle.write(toxml(xtree))

        # 3. Update the BibleData.proPref
        bible_data_entry = '|'.join([folder_id, overwrite_abbr, name, "1"])
        bibledata_json.append(bible_data_entry)
        bibledata_contents_new = "InstalledBiblesNew=" + json.dumps(bibledata_json) + ';\n'

        with open(bible_data_propref_loc, "w", encoding='utf-8') as bibledata_handle:
            bibledata_handle.write(bibledata_contents_new)

if __name__ == '__main__':
    os.makedirs(download_folder, exist_ok=True)

    click.echo("Which language would you want to download?")
    language = choose_language()
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


    dialog = radiolist_dialog(
            "ProPresenter for Windows has two options to load bibles",
             "1. Overwriting a free bible (Recommended) - The bible that was just downloaded will overwrite this Bible\n2. Sideloading the Bible (Only for advanced users) - This will make sure ProPresenter will load the Bible upon startup. Disadvantages are; potential disk storage leaks and existing bibles might go missing.",
             values=[(1,'Overwrite (recommended)'), (0,'Sideload')])
    if platform.system() == "Windows" and dialog.run() == 1:
            overwrite_free_bible(output_folder)
    else:
        # create zip of bible files
        zip_location = os.path.join(output_folder, f"../{selected_bible_abbeviation}.rvbible")
        shutil.make_archive(zip_location, 'zip', output_folder)
        rvbible_location = shutil.move(zip_location + ".zip", zip_location)

        print("Moving bible to ProPresenter directory")

        move_rvbible_propresenter_folder(rvbible_location)

    print("Done! Please restart ProPresenter and check if the bible is correctly installed.")
    input("Press enter to close...")