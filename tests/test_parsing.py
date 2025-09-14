import pytest
from propresenter_bible.parsing.html_to_usx import HtmlToUsxParser


def test_parse_verse_numbers_single():
    p = HtmlToUsxParser()
    assert p.parse_verse_numbers("5", None) == ["5"]


def test_parse_verse_numbers_range():
    p = HtmlToUsxParser()
    # Returns a list preserving endpoints and intermediate numeric values
    assert p.parse_verse_numbers("3-5", None) == ["3", 4, "5"]


def test_cleanup_whitespace_and_punct():
    p = HtmlToUsxParser()
    text = ' In the beginning  ,  God created  . '
    cleaned = p.cleanup_verse_contents(text)
    # removes duplicate spaces around punctuation
    assert cleaned == 'In the beginning, God created.'

