"""Cross-mod string collection for combined AI batching.

Gathers every source string that still needs translation across all mods and
files up front, so they can be translated in large combined batches (filling
the cache) instead of one tiny request per mod.
"""
import json
import os
import zipfile

from mineai.constants import BOOK_PATH_MARKERS, RESEARCH_PATH_MARKERS
from mineai.json_utils import load_lenient_json
from mineai.processors.locale_keys import collect_book_json_pending, collect_lang_keys_to_translate
from mineai.processors.snbt_extract import extract_snbt_strings
from mineai.runtime.state import JobState
from mineai.text_processing import already_translated


class PendingCollector:
    """Read-only traversal that yields unique untranslated source strings."""

    def __init__(self, state: JobState) -> None:
        self.state = state
        self._seen: set[str] = set()
        self._texts: list[str] = []

    def _add(self, text: str) -> None:
        if text and text not in self._seen:
            self._seen.add(text)
            self._texts.append(text)

    def collect(
        self,
        jar_files: list[str],
        loose_files: list[str],
        snbt_files: list[str],
        *,
        target_lang: dict,
        mode: str,
        translate_mods: bool,
        translate_books: bool,
        translate_quests: bool,
    ) -> list[str]:
        for path in jar_files:
            if not self.state.should_run():
                return self._texts
            self.state.wait_if_paused()
            self._collect_jar(path, target_lang, mode, translate_mods, translate_books)

        for path in loose_files:
            if not self.state.should_run():
                return self._texts
            self.state.wait_if_paused()
            self._collect_loose(path, target_lang, mode)

        if translate_quests:
            for path in snbt_files:
                if not self.state.should_run():
                    return self._texts
                self.state.wait_if_paused()
                self._collect_snbt(path, target_lang, mode)

        return self._texts

    def _collect_jar(self, jar_path, target_lang, mode, translate_mods, translate_books) -> None:
        target_file = f"{target_lang['file']}.json"
        try:
            with zipfile.ZipFile(jar_path, "r") as zin:
                locale = {
                    i.filename.lower(): i
                    for i in zin.infolist()
                    if target_file in i.filename.lower()
                    or f"/{target_lang['file']}/" in i.filename.lower()
                }
                for item in zin.infolist():
                    fl = item.filename.lower()
                    is_book_json = fl.endswith(".json") and (
                        ("/en_us/" in fl and any(m in fl for m in BOOK_PATH_MARKERS))
                        or any(m in fl for m in RESEARCH_PATH_MARKERS)
                    )
                    is_lang = fl.endswith("en_us.json") and not is_book_json

                    if translate_mods and is_lang:
                        self._collect_lang_entry(zin, item, locale, target_file, target_lang, mode)
                    elif translate_books and is_book_json:
                        self._collect_book_json(zin, item, locale, target_lang, mode)
        except (OSError, zipfile.BadZipFile):
            pass

    def _collect_lang_entry(self, zin, item, locale, target_file, target_lang, mode) -> None:
        try:
            en_data = load_lenient_json(zin.read(item))
        except (json.JSONDecodeError, OSError):
            return
        tr_key = item.filename.lower().replace("en_us.json", target_file)
        tr_data = {}
        if tr_key in locale:
            try:
                tr_data = load_lenient_json(zin.read(locale[tr_key]))
            except (json.JSONDecodeError, OSError):
                tr_data = {}
        for value in collect_lang_keys_to_translate(en_data, tr_data, mode, target_lang["regex"]).values():
            self._add(value)

    def _collect_book_json(self, zin, item, locale, target_lang, mode) -> None:
        tr_key = item.filename.lower().replace("/en_us/", f"/{target_lang['file']}/")
        try:
            en_data = load_lenient_json(zin.read(item))
        except (json.JSONDecodeError, OSError):
            return
        tr_data = {}
        if tr_key in locale:
            try:
                tr_data = load_lenient_json(zin.read(locale[tr_key]))
            except (json.JSONDecodeError, OSError):
                tr_data = {}
        pending, en_map = collect_book_json_pending(en_data, tr_data, mode)
        if not en_map:
            return
        if mode == "skip" and len(pending) <= len(en_map) * 0.1:
            return
        for value in pending.values():
            self._add(value)

    def _collect_loose(self, file_path, target_lang, mode) -> None:
        tr_disk = file_path.replace("en_us.json", f"{target_lang['file']}.json")
        try:
            with open(file_path, encoding="utf-8") as f:
                en_data = load_lenient_json(f.read().encode("utf-8"))
            tr_data = {}
            if os.path.exists(tr_disk):
                with open(tr_disk, encoding="utf-8") as f:
                    tr_data = load_lenient_json(f.read().encode("utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for value in collect_lang_keys_to_translate(en_data, tr_data, mode, target_lang["regex"]).values():
            self._add(value)

    def _collect_snbt(self, file_path, target_lang, mode) -> None:
        target_regex = target_lang["regex"]
        backup = file_path + ".bak"
        source_path = file_path
        if mode != "append" and os.path.exists(backup):
            source_path = backup
        try:
            with open(source_path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return

        if mode == "skip":
            try:
                with open(file_path, encoding="utf-8") as f:
                    if already_translated(f.read(), target_regex):
                        return
            except OSError:
                pass

        skip_regex = target_regex if mode == "append" else None
        for value in extract_snbt_strings(content, skip_translated_regex=skip_regex):
            self._add(value)
