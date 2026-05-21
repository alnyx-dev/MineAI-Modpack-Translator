import json
import os
import re
import zipfile

from mineai.constants import BOOK_PATH_MARKERS, MD_PATH_MARKERS, RESEARCH_PATH_MARKERS
from mineai.json_utils import iter_translatable_strings, load_lenient_json
from mineai.processors.snbt_extract import extract_snbt_strings
from mineai.runtime.state import JobState
from mineai.text_processing import apply_smart_glue, is_technical_term, looks_like_source_language


class StringEstimator:
    def __init__(self, state: JobState) -> None:
        self.state = state

    def estimate(
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
        smart_glue: bool,
    ) -> int:
        total = 0
        target_file = f"{target_lang['file']}.json"
        target_regex = target_lang["regex"]

        for path in jar_files:
            if not self.state.should_run():
                return total
            self.state.wait_if_paused()
            total += self._estimate_jar(
                path, target_file, target_lang, mode, translate_mods, translate_books, smart_glue
            )

        for path in loose_files:
            if not self.state.should_run():
                return total
            total += self._estimate_loose(path, target_file, mode)

        if translate_quests:
            for path in snbt_files:
                if not self.state.should_run():
                    return total
                total += self._estimate_snbt(path, mode, target_regex)

        return total

    def _estimate_jar(
        self, path, target_file, target_lang, mode, translate_mods, translate_books, smart_glue
    ) -> int:
        count = 0
        try:
            with zipfile.ZipFile(path, "r") as zin:
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
                    is_book_md = (fl.endswith(".md") or fl.endswith(".txt")) and any(
                        m in fl for m in MD_PATH_MARKERS
                    )
                    is_lang = fl.endswith("en_us.json") and not is_book_json

                    if translate_mods and is_lang:
                        count += self._count_lang(zin, item, locale, target_file, mode)
                    elif translate_books and is_book_json:
                        count += self._count_book_json(zin, item)
                    elif translate_books and is_book_md:
                        count += self._count_book_md(zin, item, smart_glue)
        except (OSError, zipfile.BadZipFile):
            pass
        return count

    def _count_lang(self, zin, item, locale, target_file, mode) -> int:
        try:
            en = load_lenient_json(zin.read(item))
        except (json.JSONDecodeError, OSError):
            return 0
        tr_key = item.filename.lower().replace("en_us.json", target_file)
        tr = {}
        if tr_key in locale:
            try:
                tr = load_lenient_json(zin.read(locale[tr_key]))
            except (json.JSONDecodeError, OSError):
                pass
        n = 0
        for key, value in en.items():
            if not isinstance(value, str) or not looks_like_source_language(value) or is_technical_term(value):
                continue
            if mode == "force" or not (key in tr and isinstance(tr[key], str) and tr[key].strip()):
                n += 1
        return n

    def _count_book_json(self, zin, item) -> int:
        try:
            data = load_lenient_json(zin.read(item))
        except (json.JSONDecodeError, OSError):
            return 0
        return sum(
            1
            for _, s in iter_translatable_strings(data)
            if s.strip() and looks_like_source_language(s) and not is_technical_term(s)
        )

    def _count_book_md(self, zin, item, smart_glue) -> int:
        try:
            text = zin.read(item).decode("utf-8-sig", errors="ignore")
        except OSError:
            return 0
        if smart_glue:
            text = apply_smart_glue(text)
        n = 0
        in_yaml = False
        for line in text.split("\n"):
            s = line.strip()
            if s == "---":
                in_yaml = not in_yaml
                continue
            if in_yaml:
                if s.lower().startswith("title:") and looks_like_source_language(line):
                    n += 1
                continue
            if s.startswith("<") or s.startswith("!["):
                continue
            if line.strip() and looks_like_source_language(line) and not is_technical_term(line):
                n += 1
        return n

    def _estimate_loose(self, path, target_file, mode) -> int:
        try:
            with open(path, encoding="utf-8") as f:
                en = load_lenient_json(f.read().encode("utf-8"))
            tr_path = path.replace("en_us.json", target_file)
            tr = {}
            if os.path.exists(tr_path):
                with open(tr_path, encoding="utf-8") as f:
                    tr = load_lenient_json(f.read().encode("utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        n = 0
        for key, value in en.items():
            if not isinstance(value, str) or not looks_like_source_language(value) or is_technical_term(value):
                continue
            if mode == "force" or not (key in tr and isinstance(tr[key], str) and tr[key].strip()):
                n += 1
        return n

    def _estimate_snbt(self, path, mode, target_regex) -> int:
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return 0
        strings = extract_snbt_strings(content)
        if mode == "force":
            return len(strings)
        return sum(1 for s in strings if not re.search(target_regex, s))
