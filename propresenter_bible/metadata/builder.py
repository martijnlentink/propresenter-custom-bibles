"""Build metadata files for the ProPresenter RVBible format."""

import os
from lxml import etree as ElementTree
from lxml.etree import Element, SubElement
from ..resources import resource_path, toxml
from ..services.api import VersionMetadata


class MetadataBuilder:
    """Constructs `metadata.xml` and `rvmetadata.xml` files from version metadata."""

    def build(self, output_file_loc: str, book_metadata: VersionMetadata) -> None:
        metadata = resource_path("metadata.xml")
        xml_tree = ElementTree.parse(metadata)

        identification_el = xml_tree.xpath("//identification")[0]
        SubElement(identification_el, "name").text = book_metadata.title
        SubElement(identification_el, "nameLocal").text = book_metadata.local_title
        SubElement(identification_el, "abbreviation").text = book_metadata.abbreviation
        SubElement(identification_el, "abbreviationLocal").text = book_metadata.local_abbreviation

        language_el = xml_tree.xpath("//language")[0]
        SubElement(language_el, "iso").text = book_metadata.language.iso_639_3
        SubElement(language_el, "name").text = book_metadata.language.name
        SubElement(language_el, "scriptDirection").text = book_metadata.language.text_direction

        book_names_el = xml_tree.xpath("//bookNames")[0]
        books_el = xml_tree.xpath("//bookList/books")[0]
        unique_short_list = []

        for book in book_metadata.books:
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
            handle.write(toxml(xml_tree))

        root = Element("RVBibleMetdata")
        SubElement(root, "name").text = book_metadata.local_title
        SubElement(root, "abbreviation").text = book_metadata.abbreviation
        SubElement(root, "displayAbbreviation").text = book_metadata.local_abbreviation
        SubElement(root, "version").text = "1"
        SubElement(root, "revision").text = "0"
        SubElement(root, "licenseType").text = "0"
        SubElement(root, "license")

        rvmetadataxml_output = os.path.join(output_file_loc, "rvmetadata.xml")
        with open(rvmetadataxml_output, 'wb') as handle:
            handle.write(toxml(root))
