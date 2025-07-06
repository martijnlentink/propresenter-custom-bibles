import os
import sys
from typing import Dict
from prompt_toolkit.completion import Completer, Completion


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath("Resources")
    return os.path.join(base_path, relative_path)


def read_yves_file(file_name: str) -> str:
    with open(file_name, "rb") as handle:
        arrayOfByte = handle.read()
        return decode_yves_bytes(arrayOfByte)


def decode_yves_bytes(input_bytes: bytes) -> str:
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
    return bytes(bArr).decode("UTF-8", errors="ignore")


class PromptCompleter(Completer):
    def __init__(self, options: Dict[str, str]):
        self._options = options

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor()
        for display_text, value in self._options.items():
            if word_before_cursor.lower() in display_text.lower():
                yield Completion(display_text, start_position=-len(word_before_cursor), display_meta=value)

