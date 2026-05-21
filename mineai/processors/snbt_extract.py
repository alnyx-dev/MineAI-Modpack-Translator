import re

from mineai.text_processing import is_translation_key, looks_like_source_language


SNBT_STRING_RE = r'"((?:[^"\\]|\\.)*)"'
SINGLE_FIELDS = ("title", "subtitle", "text", "desc", "description")
ARRAY_FIELDS = ("description", "text", "desc")


def extract_snbt_strings(content: str, *, skip_translated_regex: str | None = None) -> list[str]:
    strings: list[str] = []
    field_pattern = "|".join(SINGLE_FIELDS)
    for match in re.finditer(
        rf'(?:"|)(?:{field_pattern})(?:"|)\s*:\s*{SNBT_STRING_RE}',
        content,
        re.IGNORECASE,
    ):
        value = match.group(1)
        if not value.strip() or is_translation_key(value):
            continue
        if not looks_like_source_language(value):
            continue
        if skip_translated_regex and re.search(skip_translated_regex, value):
            continue
        strings.append(value)

    array_fields = "|".join(ARRAY_FIELDS)
    for block in re.finditer(
        rf'(?:"|)(?:{array_fields})(?:"|)\s*:\s*\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\]',
        content,
        re.IGNORECASE,
    ):
        for sm in re.finditer(SNBT_STRING_RE, block.group(0)):
            value = sm.group(1)
            if not value.strip() or is_translation_key(value):
                continue
            if not looks_like_source_language(value):
                continue
            if skip_translated_regex and re.search(skip_translated_regex, value):
                continue
            strings.append(value)
    return list(dict.fromkeys(strings))


def apply_snbt_translations(content: str, mapping: dict[str, str]) -> str:
    def replace_single(match: re.Match) -> str:
        original = match.group(2)
        translated = mapping.get(original, original)
        escaped = translated.replace("\\", "\\\\").replace('"', '\\"')
        return f'{match.group(1)}: "{escaped}"'

    field_pattern = "|".join(SINGLE_FIELDS)
    content = re.sub(
        rf'(?:"|)({field_pattern})(?:"|)\s*:\s*{SNBT_STRING_RE}',
        replace_single,
        content,
        flags=re.IGNORECASE,
    )

    def replace_array(match: re.Match) -> str:
        key = match.group(1)
        array_body = match.group(2)

        def replace_item(sm: re.Match) -> str:
            original = sm.group(1)
            translated = mapping.get(original, original)
            escaped = translated.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

        new_body = re.sub(SNBT_STRING_RE, replace_item, array_body)
        return f'{key}: {new_body}'

    array_fields = "|".join(ARRAY_FIELDS)
    content = re.sub(
        rf'(?:"|)({array_fields})(?:"|)\s*:\s*(\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\])',
        replace_array,
        content,
        flags=re.IGNORECASE,
    )
    return content
