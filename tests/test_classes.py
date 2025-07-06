import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bible_api import BibleAPI
from bible_downloader import BibleDownloader
from bible_converter import BibleConverter
from config import DEFAULT_CONFIG
from propresenter_bible_data import ProPresenterBibleData
from dtos import InstalledBible


class DummyResp:
    def __init__(self, text=None, json_data=None):
        self.text = text
        self._json = json_data or {}

    def json(self):
        return self._json


def test_retrieve_api_id(monkeypatch):
    html = '<script id="__NEXT_DATA__">{"buildId":"123"}</script>'

    def fake_get(url):
        return DummyResp(text=f"<html>{html}</html>")

    monkeypatch.setattr('bible_api.get', fake_get)
    api = BibleAPI(DEFAULT_CONFIG)
    downloader = BibleDownloader(api, DEFAULT_CONFIG)
    assert downloader.retrieve_api_id() == '123'


def test_retrieve_bibles_for_language(monkeypatch):
    data = {"response": {"data": {"versions": [{"id": 1, "title": "T", "local_title": "T", "abbreviation": "T", "local_abbreviation": "LT"}]}}}

    def fake_get(url, headers=None):
        return DummyResp(json_data=data)

    monkeypatch.setattr('bible_api.get', fake_get)
    api = BibleAPI(DEFAULT_CONFIG)
    downloader = BibleDownloader(api, DEFAULT_CONFIG)
    result = downloader.retrieve_bibles_for_language('eng')
    assert 1 in result and result[1].title == 'T'


def test_cleanup_verse_contents():
    converter = BibleConverter(DEFAULT_CONFIG)
    text = "  In the beginning ,  God created  the heavens  and the earth .  "
    cleaned = converter.cleanup_verse_contents(text)
    assert cleaned == ' In the beginning, God created the heavens and the earth.'


def test_parse_verse_numbers_range():
    converter = BibleConverter(DEFAULT_CONFIG)
    res = converter.parse_verse_numbers('1-3', None)
    assert res == ['1', 2, '3']


def test_bible_data_store(tmp_path):
    file_path = tmp_path / "BibleData.proPref"
    store = ProPresenterBibleData(str(file_path))
    assert store.entries == []
    entry = InstalledBible("id1", "ABC", "Name", "1")
    store.add_entry(entry)
    store_reloaded = ProPresenterBibleData(str(file_path))
    assert len(store_reloaded.entries) == 1
    assert store_reloaded.entries[0].abbreviation == "ABC"

