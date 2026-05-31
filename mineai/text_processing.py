import json
import re
from functools import lru_cache

from mineai.constants import DICT_FILE, IGNORE_TERMS

FORMAT_PATTERN = re.compile(
    r"("
    r"\$\([^)]+\)|"
    r"[&§][0-9a-fk-orlmn]|"
    r"<[^>]+>|"
    r"\{[^\}]+\}|"
    r"\]\([^)]+\)|"
    r"!\[[^\]]*\]|"
    r"\[[a-z0-9_.-]+:[a-z0-9_./-]+\]|"
    r"\([a-z0-9_.-]+:[a-z0-9_./-]+\)|"
    r"\([A-Za-z0-9_./-]+\.md[#a-zA-Z0-9_-]*\)|"
    r"\n|"
    r"%[0-9.,]*\$?[a-zA-Z%]"
    r")",
    flags=re.IGNORECASE,
)

IGNORE_PATTERN = re.compile(
    r"(?<![a-zA-Z])(" + "|".join(re.escape(t) for t in IGNORE_TERMS) + r")(?![a-zA-Z])"
)

# Unicode ranges for scripts that must NOT appear in a translation
# unless the target language itself uses that script.
# Catches the common "AI hallucination" of inserting random CJK glyphs.
FOREIGN_SCRIPT_PATTERN = re.compile(
    r"["
    r"\u3040-\u309F"   # Hiragana (Japanese)
    r"\u30A0-\u30FF"   # Katakana (Japanese)
    r"\u31F0-\u31FF"   # Katakana Phonetic Extensions
    r"\u4E00-\u9FFF"   # CJK Unified Ideographs (Chinese / Kanji)
    r"\u3400-\u4DBF"   # CJK Extension A
    r"\uF900-\uFAFF"   # CJK Compatibility Ideographs
    r"\uAC00-\uD7AF"   # Hangul Syllables (Korean)
    r"\u1100-\u11FF"   # Hangul Jamo
    r"\u3130-\u318F"   # Hangul Compatibility Jamo
    r"]"
)

TRANSLATABLE_TERM_WORDS = {
    "altar", "alternator", "anvil", "armor", "armour", "block", "book", "brick", "bricks",
    "chamber", "crystal", "crystals", "door", "dungeon", "emitter", "eye", "eyes", "filter",
    "forge", "fruit", "key", "keys", "machine", "mine", "mines", "mob", "mobs", "oil",
    "pillar", "realm", "ritual", "rituals", "room", "rune", "runes", "sigil", "soul",
    "spike", "stone", "stones", "tool", "tools", "trap", "upgrade",
}


def apply_smart_glue(text: str) -> str:
    if not text:
        return text
    return re.sub(
        r"(?<![.!?>\]:])\s*(?:\n|\r?\n)\s*(?!(?:[\r\n\-*#<]|$|---|[\w\s]+:))",
        " ",
        text,
    )


def load_dictionary() -> dict[str, str]:
    if not __import__("os").path.exists(DICT_FILE):
        default = {"полуслой": "плита", "сыромятная медь": "сырая медь"}
        with open(DICT_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=4)
        return default
    try:
        with open(DICT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


TERMINOLOGY_FIXES = load_dictionary()


def polish_translation(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    text = re.sub(r"([&§][0-9a-fk-or])\s+", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([&§][r])", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s+(%\d*\$?[sd])\s+\]", r"[\1]", text)
    text = re.sub(r"\(\s+(%\d*\$?[sd])\s+\)", r"(\1)", text)
    text = re.sub(r'\"\s+(%\d*\$?[sd])\s+\"', r'"\1"', text)
    text = re.sub(r"%\s+([sd])", r"%\1", text)
    text = re.sub(r"%\s+(\d+)\s*\$\s*([sd])", r"%\1$\2", text)
    text = re.sub(r"%\s*\.\s*(\d+)\s*([fd])", r"%.\1\2", text)
    text = re.sub(r"\]\s+\(", "](", text)
    text = re.sub(r"!\s+\[", "![", text)
    text = re.sub(r"\[\s+", "[", text)
    text = re.sub(r"\s+\]", "]", text)
    text = re.sub(r" {2,}", " ", text)

    for wrong, right in TERMINOLOGY_FIXES.items():

        def repl(match, r=right):
            word = match.group(0)
            if word.istitle():
                return r.capitalize()
            if word.isupper():
                return r.upper()
            return r

        text = re.sub(r"\b" + re.escape(wrong) + r"\b", repl, text, flags=re.IGNORECASE)
    return text


def mask_protected_fragments(text: str) -> tuple[str, dict[str, str]]:
    """Replace format codes and protected terms with [#n#] placeholders."""
    mapping: dict[str, str] = {}

    def replacer(match: re.Match) -> str:
        token = f"[#{len(mapping)}#]"
        mapping[token] = match.group(0)
        return token

    masked = IGNORE_PATTERN.sub(replacer, FORMAT_PATTERN.sub(replacer, text))
    masked = re.sub(r"\s+", " ", masked).strip()
    return masked, mapping


def unmask_translation(text: str, mapping: dict[str, str]) -> str:
    for token, original in mapping.items():
        idx = token.strip("#[]")
        text = re.sub(rf"\[\s*#\s*{re.escape(idx)}\s*#\s*\]", lambda _m, o=original: o, text)
    return text


def has_translatable_source_text(text: str) -> bool:
    masked, _mapping = mask_protected_fragments(text)
    stripped = re.sub(r"\[\s*#\s*\d+\s*#\s*\]", " ", masked)
    return bool(re.search(r"[a-zA-Z]", stripped))


def should_validate_ai_translation(text: str) -> bool:
    masked, _mapping = mask_protected_fragments(text)
    stripped = re.sub(r"\[\s*#\s*\d+\s*#\s*\]", " ", masked)
    words = re.findall(r"[A-Za-z][A-Za-z']*", stripped)
    if not words:
        return False
    if len(words) >= 4:
        return True
    lowercase_words = [word for word in words if re.search(r"[a-z]", word)]
    if len(lowercase_words) >= 3:
        return True
    if len(lowercase_words) >= 2 and any(
        word.casefold().strip("'") in TRANSLATABLE_TERM_WORDS for word in lowercase_words
    ):
        return True
    return False


def has_foreign_script(text: str, target_lang: dict | None = None) -> bool:
    """Return True if the text contains CJK characters and the target
    language is NOT itself a CJK language. Used to detect AI hallucinations
    that contaminate translations with random Chinese/Japanese/Korean glyphs.
    """
    if not isinstance(text, str) or not text:
        return False
    if target_lang:
        api = str(target_lang.get("api", "")).lower()
        if api in {"zh-cn", "zh-tw", "ja", "ko"}:
            return False
    return bool(FOREIGN_SCRIPT_PATTERN.search(text))


def is_probably_untranslated(source_text: str, translated_text: str, target_lang: dict | None = None) -> bool:
    if not isinstance(source_text, str) or not isinstance(translated_text, str):
        return False
    if not source_text.strip() or not translated_text.strip():
        return False
    # Reject any AI output contaminated with foreign-script characters
    # (e.g. random Chinese/Japanese/Korean glyphs) when the target language
    # is not itself CJK. Forces the retry pipeline to re-translate the entry.
    if has_foreign_script(translated_text, target_lang):
        return True
    if not has_translatable_source_text(source_text):
        return False
    if not should_validate_ai_translation(source_text):
        return False
    source_norm = re.sub(r"\s+", " ", source_text).strip().casefold()
    translated_norm = re.sub(r"\s+", " ", translated_text).strip().casefold()
    if source_norm == translated_norm:
        return True

    if not target_lang:
        return False
    api_code = str(target_lang.get("api", "")).lower()
    if api_code == "ru":
        return not re.search(target_lang["regex"], translated_text)
    if api_code in {"zh-cn", "ja", "ko"}:
        return not re.search(target_lang["regex"], translated_text)
    return False


@lru_cache(maxsize=10000)
def is_technical_term(text: str) -> bool:
    if not text:
        return True
    lower = text.lower()
    if not re.search(r"[a-z]", lower):
        return True
    if re.match(r"^[a-z0-9_.-]+$", lower) and any(c in lower for c in "._"):
        return True
    prefixes = (
        "glyph_", "ritual_", "familiar_", "source_", "mana_", "spell_",
        "effect_", "rune_", "altar_", "botania_", "create_", "kubejs_",
    )
    return any(lower.startswith(p) for p in prefixes)


def is_translation_key(text: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]+[.:][a-zA-Z0-9_.-]+$", text.strip()))


def looks_like_source_language(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z]", text))


def already_translated(text: str, target_regex: str) -> bool:
    return bool(re.search(target_regex, text))
