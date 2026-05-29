"""Универсальный OpenAI-совместимый движок (для localhost, OpenCode Zen и т.п.)."""
from __future__ import annotations

import json
import time

import requests

from mineai.engines.llm_common import BatchLlmEngine


class CustomLlmEngine(BatchLlmEngine):
    """Любой эндпоинт с интерфейсом ``/v1/chat/completions``.

    Поддерживается передача:
      * Bearer-ключа через ``Authorization``;
      * произвольных доп. заголовков (JSON-словарь, например ``{"X-API-Key": "..."}``).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider_name: str = "Custom",
        extra_headers: str = "",
        auth_scheme: str = "bearer",
        mode: str = "safe",
        context: str = "",
        glossary: dict[str, str] | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.base_url = (base_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.provider_name = (provider_name or "Custom").strip()
        self.auth_scheme = (auth_scheme or "bearer").strip().lower()
        self._extra_headers = self._parse_headers(extra_headers)
        super().__init__(
            mode=mode,
            context=context,
            call_api=self._request,
            label=self.provider_name or "Custom",
            glossary=glossary,
            batch_size=batch_size,
        )

    @staticmethod
    def _parse_headers(raw: str) -> dict[str, str]:
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except (json.JSONDecodeError, TypeError):
            pass
        return {}

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            scheme = self.auth_scheme
            if scheme == "bearer":
                headers["Authorization"] = f"Bearer {self.api_key}"
            elif scheme == "x-api-key":
                headers["X-API-Key"] = self.api_key
            elif scheme == "api-key":
                headers["api-key"] = self.api_key
            elif scheme == "none":
                pass
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self._extra_headers)
        return headers

    def _resolve_url(self) -> str:
        url = self.base_url
        if not url:
            raise ValueError("Не задан Base URL для custom-провайдера")
        if "/chat/completions" in url:
            return url
        return url.rstrip("/") + "/chat/completions"

    def _request(self, prompt: str, max_tokens: int) -> str | None:
        url = self._resolve_url()
        max_retries = 3
        base_delay = 1.0  # лёгкая пауза для совместимости

        last_error: str | None = None
        for attempt in range(max_retries):
            time.sleep(base_delay if attempt == 0 else 0)
            try:
                response = requests.post(
                    url,
                    headers=self._headers(),
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": max_tokens,
                    },
                    timeout=300,
                )
            except requests.RequestException as exc:
                last_error = f"network: {exc}"
                if attempt + 1 < max_retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise

            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(
                    f"\n[{self.provider_name}] 429 Rate limit. Жду {wait} сек "
                    f"(попытка {attempt + 1}/{max_retries})..."
                )
                time.sleep(wait)
                continue

            if not response.ok:
                detail = response.text[:200] if response.text else response.reason
                raise requests.HTTPError(
                    f"{response.status_code}: {detail}", response=response
                )

            try:
                data = response.json()
            except ValueError as exc:
                last_error = f"invalid json: {exc}"
                if attempt + 1 < max_retries:
                    continue
                return None

            # OpenAI-совместимый ответ
            choices = data.get("choices") or []
            if not choices:
                # Поддержка простых API: { "content": "..." } или { "response": "..." }
                content = data.get("content") or data.get("response")
                return str(content).strip() if content else None
            message = choices[0].get("message") or {}
            content = message.get("content")
            if content is None:
                # Некоторые сервисы кладут ответ в "text"
                content = choices[0].get("text")
            if content is None:
                print(
                    f"\n[{self.provider_name}] пустой ответ "
                    "(возможно, сработал фильтр модели)."
                )
                return None
            return str(content).strip()

        if last_error:
            print(f"\n[{self.provider_name}] не удалось получить ответ: {last_error}")
        return None
