"""UI prompting helpers for interactive CLI flows."""

from typing import Dict
from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from ..services.api import BibleApiClient, LanguagesItem, LanguagesResponse


class PromptCompleter(Completer):
    """Simple autocomplete for prompt_toolkit backed by a string map."""

    def __init__(self, options: Dict[str, str]):
        self._options = options

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor()
        for display_text, value in self._options.items():
            if word_before_cursor.lower() in display_text.lower():
                yield Completion(display_text, start_position=-len(word_before_cursor), display_meta=value)


def choose_language(api: BibleApiClient) -> str:
    """Prompt interactive language selection using the typed API client."""
    languages: LanguagesResponse = api.get_languages_config()
    lang_versions = languages.default_versions

    def gen_name(lang_version: LanguagesItem):
        local_name = lang_version.local_name
        name = lang_version.name
        return local_name if local_name == name else f"{local_name} ({name})"

    prompt_options = {gen_name(x): x.language_tag for x in lang_versions}
    print("Choose the language you want to retrieve")
    while True:
        choice = prompt('Type to filter: ', completer=PromptCompleter(prompt_options))
        lang_code = next((x[1] for x in prompt_options.items() if x[0].lower() == choice.lower()), None)
        if lang_code is not None:
            return lang_code
        print("Please select a valid language from the list. Press TAB to select.")
