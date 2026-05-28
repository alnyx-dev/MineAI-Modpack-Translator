import json
import re
from typing import Callable

import requests

from mineai.engines.base import EngineCallbacks, EngineItem, TranslationEngine
from mineai.text_processing import polish_translation, unmask_translation

GLOSSARY_ADDITIONS_KEY = "__glossary_additions__"


def _glossary_block(glossary: dict[str, str] | None) -> str:
    if not glossary:
        return ""
    pairs = json.dumps(glossary, ensure_ascii=False)
    return (
        "\nГЛОССАРИЙ (обязательные соответствия EN→RU, используй их дословно): "
        f"{pairs}.\n"
    )


def _glossary_instruction(allow_additions: bool) -> str:
    if not allow_additions:
        return ""
    return (
        " Если встречаешь НОВЫЕ устойчивые термины (имена предметов, блоков, мобов, "
        "названия машин/мультиблоков), которые стоит зафиксировать на будущее — добавь "
        f'их в дополнительный ключ "{GLOSSARY_ADDITIONS_KEY}" того же JSON-объекта в '
        'формате {"English term": "русский перевод"}. Не дублируй термины из глоссария.'
    )


def build_translation_prompt(
    payload: dict[str, str],
    lang_name: str,
    *,
    mode: str,
    context: str,
    glossary: dict[str, str] | None = None,
    allow_glossary_additions: bool = False,
) -> str:
    blob = json.dumps(payload, ensure_ascii=False)
    glossary_text = _glossary_block(glossary)
    additions = _glossary_instruction(allow_glossary_additions)
    if mode == "context" and context:
        return (
            f"Ты локализатор Minecraft. Переведи строки мода/квеста «{context}» на {lang_name}. "
            f"Сохраняй игровой стиль и лор. Не переводи JSON-ключи. Теги [#0#] не менять."
            f"{glossary_text}"
            f" Верни ТОЛЬКО валидный JSON с теми же ключами.{additions}"
            f" Данные: {blob}"
        )
    return (
        f"Translate JSON string values from English to {lang_name}. "
        f"Do not translate keys. Preserve [#0#] tags exactly."
        f"{glossary_text}"
        f" Return ONLY valid JSON with the same keys.{additions}"
        f" Data: {blob}"
    )


def parse_llm_json_response(content: str) -> dict:
    text = re.sub(r"^```json\s*|^```\s*|```$", "", content.strip(), flags=re.IGNORECASE).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("LLM response is not a JSON object")
    return data


def extract_glossary_additions(payload: dict) -> dict[str, str]:
    """Достать и вычистить ``__glossary_additions__`` из ответа модели."""
    raw = payload.pop(GLOSSARY_ADDITIONS_KEY, None)
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str) or not isinstance(v, (str, int, float)):
            continue
        src = k.strip()
        dst = str(v).strip()
        if src and dst and src.lower() != dst.lower():
            cleaned[src] = dst
    return cleaned


class BatchLlmEngine(TranslationEngine):
    """Batched JSON translation via any chat-completions API."""

    def __init__(
        self,
        *,
        mode: str = "safe",
        context: str = "",
        call_api: Callable[[str, int], str | None],
        label: str = "ИИ",
        glossary: "GlossaryAdapter | None" = None,
    ) -> None:
        self.mode = mode
        self.context = context
        self._call_api = call_api
        self.label = label
        self.glossary = glossary
        self.batch_size = 40 if mode == "context" else 20
        self.max_tokens = 4096 if mode == "context" else 2048

    def translate_batch(
        self,
        items: dict[str, EngineItem],
        target_lang: dict,
        callbacks: EngineCallbacks,
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        keys = list(items.keys())
        i = 0
        while i < len(keys) and callbacks.should_run():
            callbacks.wait_if_paused()
            chunk = keys[i : i + self.batch_size]
            if not self._translate_chunk(chunk, items, target_lang, result, callbacks):
                callbacks.on_log(f"❌ Ошибка {self.label}. Дробим пакет...", "yellow")
                for j in range(0, len(chunk), 10):
                    sub = chunk[j : j + 10]
                    if not self._translate_chunk(sub, items, target_lang, result, callbacks):
                        for key in sub:
                            result[key] = items[key].original
            i += self.batch_size
        return result

    def _translate_chunk(
        self,
        chunk_keys: list[str],
        items: dict[str, EngineItem],
        target_lang: dict,
        result: dict[str, str],
        callbacks: EngineCallbacks,
    ) -> bool:
        payload = {k: items[k].masked for k in chunk_keys}
        glossary_terms = self._chunk_glossary([items[k].original for k in chunk_keys])
        allow_additions = bool(self.glossary and self.glossary.allow_additions)
        prompt = build_translation_prompt(
            payload,
            target_lang["name"],
            mode=self.mode,
            context=self.context,
            glossary=glossary_terms,
            allow_glossary_additions=allow_additions,
        )
        callbacks.on_status(f"⏳ {self.label}: пакет {len(chunk_keys)} строк...")
        try:
            content = self._call_api(prompt, self.max_tokens)
            if not content:
                return False
            translated = parse_llm_json_response(content)
            additions = extract_glossary_additions(translated)
            if additions and self.glossary:
                added = self.glossary.stage(additions)
                if added:
                    callbacks.on_log(
                        f"📖 Глоссарий: ИИ предложил {added} новых термина(ов)",
                        "magenta",
                    )
            for key in chunk_keys:
                if key in translated:
                    text = unmask_translation(str(translated[key]), items[key].mapping)
                    result[key] = polish_translation(text)
                else:
                    result[key] = items[key].original
            return True
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            callbacks.on_log(f"❌ {self.label}: неверный JSON — {exc}", "red")
            return False
        except requests.RequestException as exc:
            callbacks.on_log(f"❌ {self.label}: сеть — {exc}", "red")
            return False

    def _chunk_glossary(self, originals: list[str]) -> dict[str, str]:
        if not self.glossary:
            return {}
        return self.glossary.relevant_for(originals)
