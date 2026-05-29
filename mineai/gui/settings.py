import os

import customtkinter as ctk
from tkinter import filedialog

from mineai.config import ConfigManager
from mineai.constants import CUSTOM_AUTH_SCHEMES, DEFAULT_OPENROUTER_MODEL


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, config: ConfigManager, on_saved) -> None:
        super().__init__(parent)
        self.config = config
        self.on_saved = on_saved
        self.title("⚙ Настройки MineAI")
        self.geometry("560x780")
        self.resizable(False, False)
        self.grab_set()

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=10)
        tab_ai = tabs.add("Локальный ИИ")
        tab_or = tabs.add("OpenRouter")
        tab_custom = tabs.add("Custom AI")
        tab_gloss = tabs.add("Глоссарий")
        tab_gen = tabs.add("Общие и API")

        self._build_local_ai_tab(tab_ai)
        self._build_openrouter_tab(tab_or)
        self._build_custom_tab(tab_custom)
        self._build_glossary_tab(tab_gloss)
        self._build_general_tab(tab_gen)

        ctk.CTkButton(
            self,
            text="💾 Сохранить настройки",
            fg_color="#28a745",
            hover_color="#218838",
            command=self._save,
        ).pack(fill="x", padx=20, pady=10)

    # ------------------------------------------------------------------ tabs

    def _build_local_ai_tab(self, tab) -> None:
        ctk.CTkLabel(tab, text="Исполняемый файл KoboldCPP (.exe):", font=("", 12, "bold")).pack(
            anchor="w", pady=(10, 0), padx=10
        )
        self.ent_ai_exe = ctk.CTkEntry(tab, width=360)
        self.ent_ai_exe.insert(0, self.config.get("AI", "exe_path"))
        self.ent_ai_exe.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(
            tab,
            text="Обзор",
            width=80,
            command=lambda: self._browse(self.ent_ai_exe, [("Executables", "*.exe")]),
        ).pack(anchor="e", padx=10)

        ctk.CTkLabel(tab, text="Модель (.gguf):", font=("", 12, "bold")).pack(
            anchor="w", pady=(10, 0), padx=10
        )
        self.ent_ai_mod = ctk.CTkEntry(tab, width=360)
        self.ent_ai_mod.insert(0, self.config.get("AI", "model_path"))
        self.ent_ai_mod.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(
            tab,
            text="Обзор",
            width=80,
            command=lambda: self._browse(self.ent_ai_mod, [("GGUF Models", "*.gguf")]),
        ).pack(anchor="e", padx=10)

        gpu_val = self.config.getint("AI", "gpu_layers", 99)
        self.lbl_gpu = ctk.CTkLabel(tab, text=f"Слои GPU: {gpu_val}", font=("", 12, "bold"))
        self.lbl_gpu.pack(anchor="w", pady=(10, 0), padx=10)
        self.slider_gpu = ctk.CTkSlider(
            tab,
            from_=0,
            to=99,
            number_of_steps=99,
            command=lambda v: self.lbl_gpu.configure(text=f"Слои GPU: {int(v)}"),
        )
        self.slider_gpu.set(gpu_val)
        self.slider_gpu.pack(fill="x", padx=10, pady=5)

    def _build_openrouter_tab(self, tab) -> None:
        ctk.CTkLabel(
            tab,
            text="Ключ: openrouter.ai/keys",
            font=("", 11),
            text_color="gray",
        ).pack(anchor="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(tab, text="API ключ OpenRouter:", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(5, 0)
        )
        self.ent_or_key = ctk.CTkEntry(tab, show="*")
        self.ent_or_key.insert(0, self.config.get("OPENROUTER", "api_key"))
        self.ent_or_key.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            tab, text="ID модели (напр. qwen/qwen-2.5-72b-instruct):", font=("", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        self.ent_or_model = ctk.CTkEntry(tab)
        self.ent_or_model.insert(0, self.config.get("OPENROUTER", "model") or DEFAULT_OPENROUTER_MODEL)
        self.ent_or_model.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            tab, text="Site URL (необязательно, для статистики):", font=("", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(10, 0))
        self.ent_or_site = ctk.CTkEntry(tab)
        self.ent_or_site.insert(0, self.config.get("OPENROUTER", "site_url"))
        self.ent_or_site.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab, text="Название приложения (X-Title):", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.ent_or_app = ctk.CTkEntry(tab)
        self.ent_or_app.insert(0, self.config.get("OPENROUTER", "app_name"))
        self.ent_or_app.pack(fill="x", padx=10, pady=5)

    def _build_custom_tab(self, tab) -> None:
        ctk.CTkLabel(
            tab,
            text="Любой OpenAI-совместимый эндпоинт: localhost, OpenCode Zen,\n"
            "Ollama (/v1), LM Studio, llama.cpp server, vLLM и т.д.",
            font=("", 11),
            text_color="gray",
            justify="left",
        ).pack(anchor="w", padx=10, pady=(10, 0))

        ctk.CTkLabel(tab, text="Имя провайдера (отображается в логе):", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.ent_cu_name = ctk.CTkEntry(tab)
        self.ent_cu_name.insert(0, self.config.get("CUSTOM_AI", "name"))
        self.ent_cu_name.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            tab,
            text="Base URL (до /chat/completions; обычно заканчивается на /v1):",
            font=("", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 0))
        self.ent_cu_url = ctk.CTkEntry(tab)
        self.ent_cu_url.insert(0, self.config.get("CUSTOM_AI", "base_url"))
        self.ent_cu_url.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab, text="API ключ (если нужен):", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.ent_cu_key = ctk.CTkEntry(tab, show="*")
        self.ent_cu_key.insert(0, self.config.get("CUSTOM_AI", "api_key"))
        self.ent_cu_key.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab, text="ID модели:", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.ent_cu_model = ctk.CTkEntry(tab)
        self.ent_cu_model.insert(0, self.config.get("CUSTOM_AI", "model"))
        self.ent_cu_model.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab, text="Схема авторизации:", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 0)
        )
        self.var_cu_auth = ctk.StringVar(
            value=self.config.get("CUSTOM_AI", "auth_scheme") or "bearer"
        )
        ctk.CTkOptionMenu(
            tab, variable=self.var_cu_auth, values=list(CUSTOM_AUTH_SCHEMES)
        ).pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            tab,
            text='Доп. заголовки (JSON, напр. {"X-Provider":"opencode"}):',
            font=("", 12, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 0))
        self.ent_cu_headers = ctk.CTkEntry(tab)
        self.ent_cu_headers.insert(0, self.config.get("CUSTOM_AI", "extra_headers"))
        self.ent_cu_headers.pack(fill="x", padx=10, pady=5)

    def _build_glossary_tab(self, tab) -> None:
        self.var_gl_enabled = ctk.BooleanVar(value=self.config.getboolean("GLOSSARY", "enabled"))
        ctk.CTkSwitch(
            tab,
            text="📖 Использовать глоссарий при ИИ-переводе",
            variable=self.var_gl_enabled,
        ).pack(anchor="w", padx=10, pady=(15, 5))

        self.var_gl_append = ctk.BooleanVar(
            value=self.config.getboolean("GLOSSARY", "auto_append")
        )
        ctk.CTkSwitch(
            tab,
            text="✏️ Разрешить ИИ дописывать новые термины",
            variable=self.var_gl_append,
        ).pack(anchor="w", padx=10, pady=5)

        ctk.CTkLabel(tab, text="Путь к glossary.md:", font=("", 12, "bold")).pack(
            anchor="w", padx=10, pady=(15, 0)
        )
        self.ent_gl_path = ctk.CTkEntry(tab)
        self.ent_gl_path.insert(0, self.config.get("GLOSSARY", "path"))
        self.ent_gl_path.pack(fill="x", padx=10, pady=5)
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=10)
        ctk.CTkButton(
            row,
            text="Обзор",
            width=80,
            command=lambda: self._browse(self.ent_gl_path, [("Markdown", "*.md")]),
        ).pack(side="left")
        ctk.CTkButton(row, text="Открыть", width=80, command=self._open_glossary).pack(
            side="left", padx=(8, 0)
        )

        ctk.CTkLabel(
            tab, text="Макс. терминов в одном пакете:", font=("", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(15, 0))
        max_terms = self.config.getint("GLOSSARY", "max_terms_per_batch", 60)
        self.lbl_gl_max = ctk.CTkLabel(tab, text=f"Лимит: {max_terms}")
        self.lbl_gl_max.pack(anchor="w", padx=10)
        self.slider_gl_max = ctk.CTkSlider(
            tab,
            from_=10,
            to=200,
            number_of_steps=19,
            command=lambda v: self.lbl_gl_max.configure(text=f"Лимит: {int(v)}"),
        )
        self.slider_gl_max.set(max_terms)
        self.slider_gl_max.pack(fill="x", padx=10, pady=5)

    def _build_general_tab(self, tab) -> None:
        self.var_smart = ctk.BooleanVar(value=self.config.getboolean("GENERAL", "smart_glue"))
        ctk.CTkSwitch(tab, text="✨ Умный склейщик предложений", variable=self.var_smart).pack(
            anchor="w", padx=10, pady=15
        )

        workers = self.config.getint("GENERAL", "google_workers", 5)
        ctk.CTkLabel(tab, text="Потоки Google Translate:", font=("", 12, "bold")).pack(
            anchor="w", padx=10
        )
        self.slider_thr = ctk.CTkSlider(tab, from_=1, to=10, number_of_steps=9)
        self.slider_thr.set(workers)
        self.slider_thr.pack(fill="x", padx=10, pady=5)

        batch = self.config.getint("GENERAL", "batch_size", 40)
        self.lbl_batch = ctk.CTkLabel(
            tab, text=f"Строк в пакете ИИ: {batch}", font=("", 12, "bold")
        )
        self.lbl_batch.pack(anchor="w", padx=10, pady=(10, 0))
        ctk.CTkLabel(
            tab,
            text="Строки из разных модов объединяются в один запрос до этого лимита.",
            font=("", 10),
            text_color="gray",
            justify="left",
        ).pack(anchor="w", padx=10)
        self.slider_batch = ctk.CTkSlider(
            tab,
            from_=5,
            to=100,
            number_of_steps=19,
            command=lambda v: self.lbl_batch.configure(text=f"Строк в пакете ИИ: {int(v)}"),
        )
        self.slider_batch.set(batch)
        self.slider_batch.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab, text="API ключ DeepL:", font=("", 12, "bold")).pack(
            anchor="w", pady=(10, 0), padx=10
        )
        self.ent_deepl = ctk.CTkEntry(tab, show="*")
        self.ent_deepl.insert(0, self.config.get("API", "deepl_key"))
        self.ent_deepl.pack(fill="x", padx=10, pady=5)

    # ------------------------------------------------------------------ helpers

    def _browse(self, entry: ctk.CTkEntry, filetypes) -> None:
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _open_glossary(self) -> None:
        path = self.ent_gl_path.get().strip()
        if path and os.path.exists(path):
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except OSError:
                pass

    def _save(self) -> None:
        self.config.set("AI", "exe_path", self.ent_ai_exe.get())
        self.config.set("AI", "model_path", self.ent_ai_mod.get())
        self.config.set("AI", "gpu_layers", int(self.slider_gpu.get()))
        self.config.set("OPENROUTER", "api_key", self.ent_or_key.get())
        self.config.set("OPENROUTER", "model", self.ent_or_model.get().strip())
        self.config.set("OPENROUTER", "site_url", self.ent_or_site.get().strip())
        self.config.set("OPENROUTER", "app_name", self.ent_or_app.get().strip())
        self.config.set("CUSTOM_AI", "name", self.ent_cu_name.get().strip() or "Custom")
        self.config.set("CUSTOM_AI", "base_url", self.ent_cu_url.get().strip())
        self.config.set("CUSTOM_AI", "api_key", self.ent_cu_key.get())
        self.config.set("CUSTOM_AI", "model", self.ent_cu_model.get().strip())
        self.config.set("CUSTOM_AI", "auth_scheme", self.var_cu_auth.get())
        self.config.set("CUSTOM_AI", "extra_headers", self.ent_cu_headers.get().strip())
        self.config.set("GLOSSARY", "enabled", self.var_gl_enabled.get())
        self.config.set("GLOSSARY", "auto_append", self.var_gl_append.get())
        self.config.set("GLOSSARY", "path", self.ent_gl_path.get().strip())
        self.config.set("GLOSSARY", "max_terms_per_batch", int(self.slider_gl_max.get()))
        self.config.set("GENERAL", "smart_glue", self.var_smart.get())
        self.config.set("GENERAL", "batch_size", int(self.slider_batch.get()))
        self.config.set("GENERAL", "google_workers", int(self.slider_thr.get()))
        self.config.set("API", "deepl_key", self.ent_deepl.get())
        self.on_saved()
        self.destroy()
