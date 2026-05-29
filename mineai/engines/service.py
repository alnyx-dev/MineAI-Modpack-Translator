from mineai.cache import TranslationCache
from mineai.config import ConfigManager
from mineai.engines.base import EngineCallbacks, EngineItem, TranslationEngine
from mineai.engines.custom import CustomLlmEngine
from mineai.engines.deepl import DeepLEngine
from mineai.engines.google import GoogleEngine
from mineai.constants import DEFAULT_OPENROUTER_MODEL
from mineai.engines.kobold import KoboldEngine
from mineai.engines.openrouter import OpenRouterEngine
from mineai.glossary import Glossary
from mineai.text_processing import apply_smart_glue, is_probably_untranslated, mask_protected_fragments


class GlossaryAdapter:
    """Тонкая обёртка над ``Glossary`` для движков ИИ."""

    def __init__(
        self,
        glossary: Glossary | None,
        *,
        enabled: bool,
        allow_additions: bool,
        max_terms: int,
    ) -> None:
        self._glossary = glossary
        self.enabled = enabled and glossary is not None
        self.allow_additions = self.enabled and allow_additions
        self.max_terms = max(1, max_terms)

    def relevant_for(self, texts) -> dict[str, str]:
        if not self.enabled or not self._glossary:
            return {}
        return self._glossary.relevant_for(texts, limit=self.max_terms)

    def stage(self, additions: dict[str, str]) -> int:
        if not self.allow_additions or not self._glossary:
            return 0
        return self._glossary.stage_additions(additions)


class TranslationService:
    """Prepares strings, uses cache, delegates to a translation engine."""

    def __init__(
        self,
        engine_name: str,
        cache: TranslationCache,
        config: ConfigManager,
        *,
        google_mode: str = "single",
        ai_mode: str = "safe",
        ai_provider: str = "local",
        glossary_adapter: GlossaryAdapter | None = None,
    ) -> None:
        self.engine_name = engine_name
        self.cache = cache
        self.config = config
        self.google_mode = google_mode
        self.ai_mode = ai_mode
        self.ai_provider = ai_provider
        self.glossary = glossary_adapter
        self.batch_size = config.getint("GENERAL", "batch_size", 40)
        self.untranslated_count = 0

    def _build_engine(self, context: str = "") -> TranslationEngine:
        if self.engine_name == "google":
            return GoogleEngine(
                workers=self.config.getint("GENERAL", "google_workers", 5),
                mode=self.google_mode,
            )
        if self.engine_name == "deepl":
            return DeepLEngine(self.config.get("API", "deepl_key"))
        if self.ai_provider == "openrouter":
            return OpenRouterEngine(
                api_key=self.config.get("OPENROUTER", "api_key"),
                model=self.config.get("OPENROUTER", "model") or DEFAULT_OPENROUTER_MODEL,
                mode=self.ai_mode,
                context=context,
                site_url=self.config.get("OPENROUTER", "site_url"),
                app_name=self.config.get("OPENROUTER", "app_name"),
                glossary=self.glossary,
                batch_size=self.batch_size,
            )
        if self.ai_provider == "custom":
            return CustomLlmEngine(
                base_url=self.config.get("CUSTOM_AI", "base_url"),
                api_key=self.config.get("CUSTOM_AI", "api_key"),
                model=self.config.get("CUSTOM_AI", "model"),
                provider_name=self.config.get("CUSTOM_AI", "name"),
                extra_headers=self.config.get("CUSTOM_AI", "extra_headers"),
                auth_scheme=self.config.get("CUSTOM_AI", "auth_scheme"),
                mode=self.ai_mode,
                context=context,
                glossary=self.glossary,
                batch_size=self.batch_size,
            )
        return KoboldEngine(
            mode=self.ai_mode,
            context=context,
            glossary=self.glossary,
            batch_size=self.batch_size,
        )

    def translate_dict(
        self,
        strings: dict[str, str],
        target_lang: dict,
        callbacks: EngineCallbacks,
        *,
        context: str = "",
    ) -> dict[str, str]:
        if not strings:
            return {}

        smart_glue = self.config.getboolean("GENERAL", "smart_glue")
        result: dict[str, str] = {}
        pending: dict[str, EngineItem] = {}
        cached_count = 0

        for key, text in strings.items():
            if not callbacks.should_run():
                break
            callbacks.wait_if_paused()
            if smart_glue:
                text = apply_smart_glue(text)

            hit = self.cache.get(target_lang["api"], text)
            if hit is not None:
                if is_probably_untranslated(text, hit, target_lang):
                    self.cache.delete(target_lang["api"], text)
                    callbacks.on_log(
                        f"⚠️ Кэш устарел: строка без локализации будет переведена заново — {text[:40]}",
                        "yellow",
                    )
                else:
                    result[key] = hit
                    cached_count += 1
                    continue

            masked, mapping = mask_protected_fragments(text)
            if not masked:
                result[key] = text
                continue
            pending[key] = EngineItem(key=key, original=text, masked=masked, mapping=mapping)

        if cached_count:
            callbacks.on_log(f"   🗃️ Из кэша: {cached_count} строк", "dim")

        if not pending or not callbacks.should_run():
            return result

        engine = self._build_engine(context)
        translated = engine.translate_batch(pending, target_lang, callbacks)

        for key, text in translated.items():
            original = pending[key].original
            result[key] = text
            if is_probably_untranslated(original, text, target_lang):
                self.untranslated_count += 1
                callbacks.on_log(
                    f"⚠️ Пропуск кэша: строка осталась без локализации — {original[:40]}",
                    "yellow",
                )
            else:
                self.cache.set(target_lang["api"], original, text)
            callbacks.on_log(f" > {original[:40]} -> {text[:40]}", "dim")

        for key, item in pending.items():
            if key not in translated:
                result[key] = item.original

        self.cache.save_if_threshold()
        return result
