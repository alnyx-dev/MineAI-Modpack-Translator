import configparser
import os

from mineai.constants import GLOSSARY_FILE, SETTINGS_FILE


class ConfigManager:
    """Persistent application settings (settings.ini)."""

    _DEFAULTS = {
        "GENERAL": {
            "mc_dir": os.getcwd(),
            "theme": "Dark",
            "color": "blue",
            "smart_glue": "True",
            "google_workers": "5",
        },
        "AI": {
            "exe_path": "koboldcpp.exe",
            "model_path": "",
            "gpu_layers": "99",
            "ai_provider": "local",
        },
        "API": {
            "deepl_key": "",
        },
        "OPENROUTER": {
            "api_key": "",
            "model": "google/gemma-2-9b-it:free",
            "site_url": "",
            "app_name": "MineAI Translator",
        },
        "CUSTOM_AI": {
            "name": "My provider",
            "base_url": "http://localhost:8080/v1",
            "api_key": "",
            "model": "",
            "auth_scheme": "bearer",
            "extra_headers": "",
        },
        "GLOSSARY": {
            "enabled": "True",
            "auto_append": "True",
            "path": GLOSSARY_FILE,
            "max_terms_per_batch": "60",
        },
    }

    def __init__(self) -> None:
        self._config = configparser.ConfigParser()
        self.load()

    def load(self) -> None:
        self._config.read(SETTINGS_FILE, encoding="utf-8")
        changed = False
        for section, keys in self._DEFAULTS.items():
            if not self._config.has_section(section):
                self._config.add_section(section)
                changed = True
            for key, value in keys.items():
                if not self._config.has_option(section, key):
                    self._config.set(section, key, str(value))
                    changed = True
        if changed:
            self.save()

    def save(self) -> None:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            self._config.write(f)

    def get(self, section: str, key: str) -> str:
        return self._config.get(section, key)

    def set(self, section: str, key: str, value) -> None:
        self._config.set(section, key, str(value))
        self.save()

    def getboolean(self, section: str, key: str) -> bool:
        return self._config.getboolean(section, key)

    def getint(self, section: str, key: str, fallback: int = 0) -> int:
        raw = self.get(section, key)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return fallback


# Shared singleton for GUI and jobs
settings = ConfigManager()
