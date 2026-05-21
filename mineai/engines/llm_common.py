import json
import re
from typing import Callable

import requests

from mineai.engines.base import EngineCallbacks, EngineItem, TranslationEngine
from mineai.text_processing import polish_translation, unmask_translation


def build_translation_prompt(
    payload: dict[str, str],
    lang_name: str,
    *,
    mode: str,
    context: str,
) -> str:
    blob = json.dumps(payload, ensure_ascii=False)
    if mode == "context" and context:
        return (
            f"Ты локализатор Minecraft. Переведи строки мода/квеста «{context}» на {lang_name}. "
            f"Сохраняй игровой стиль и лор. Не переводи JSON-ключи. Теги [#0#] не менять. "
            f"Верни ТОЛЬКО валидный JSON с теми же ключами. Данные: {blob}"
        )
    return (
        f"Translate JSON string values from English to {lang_name}. "
        f"Do not translate keys. Preserve [#0#] tags exactly. "
        f"Return ONLY valid JSON with the same keys. Data: {blob}"
    )


def parse_llm_json_response(content: str) -> dict:
    text = re.sub(r"^```json\s*|^```\s*|```$", "", content.strip(), flags=re.IGNORECASE).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("LLM response is not a JSON object")
    return data


class BatchLlmEngine(TranslationEngine):
    """Batched JSON translation via any chat-completions API."""

    def __init__(
        self,
        *,
        mode: str = "safe",
        context: str = "",
        call_api: Callable[[str, int], str | None],
        label: str = "ИИ",
    ) -> None:
        self.mode = mode
        self.context = context
        self._call_api = call_api
        self.label = label
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
        prompt = build_translation_prompt(
            payload,
            target_lang["name"],
            mode=self.mode,
            context=self.context,
        )
        callbacks.on_status(f"⏳ {self.label}: пакет {len(chunk_keys)} строк...")
        try:
            content = self._call_api(prompt, self.max_tokens)
            if not content:
                return False
            translated = parse_llm_json_response(content)
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
