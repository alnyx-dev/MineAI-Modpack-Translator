import re

from mineai.json_utils import iter_translatable_strings, path_to_key
from mineai.text_processing import is_technical_term, looks_like_source_language


def collect_lang_keys_to_translate(
    en_data: dict,
    tr_data: dict,
    mode: str,
    target_regex: str,
) -> dict[str, str]:
    """Return lang file keys that still need translation."""
    pending: dict[str, str] = {}
    for key, value in en_data.items():
        if not isinstance(value, str) or not value.strip():
            continue
        if is_technical_term(value):
            continue
        if not looks_like_source_language(value):
            continue

        existing = tr_data.get(key) if isinstance(tr_data.get(key), str) else ""
        if mode == "append" and existing.strip() and existing != value:
            continue
        if mode == "append" and existing.strip() == value:
            pending[key] = value
        elif mode != "append" or not existing.strip():
            pending[key] = value
    return pending


def collect_book_json_pending(
    en_data: dict,
    tr_data: dict,
    mode: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (pending, en_map) for book/guide JSON structures.

    ``pending`` maps json-path keys to source strings still needing translation;
    ``en_map`` is every translatable source string keyed by path.
    """
    en_map = {
        path_to_key(p): s for p, s in iter_translatable_strings(en_data) if s.strip()
    }
    tr_map = (
        {path_to_key(p): s for p, s in iter_translatable_strings(tr_data)} if tr_data else {}
    )

    pending: dict[str, str] = {}
    for path_key, source in en_map.items():
        if is_technical_term(source):
            continue
        if not looks_like_source_language(source):
            continue
        existing = tr_map.get(path_key, "")
        if mode == "append" and existing.strip() and existing != source:
            continue
        pending[path_key] = source
    return pending, en_map


def count_translatable_lang_entries(en_data: dict) -> int:
    return sum(
        1
        for v in en_data.values()
        if isinstance(v, str) and looks_like_source_language(v) and not is_technical_term(v)
    )
