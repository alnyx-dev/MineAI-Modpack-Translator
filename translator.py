import os
import re
import json
import time
import zipfile
import shutil
import requests
import subprocess
import threading
import traceback
import configparser
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

# ================= ГЛОБАЛЬНЫЕ КОНСТАНТЫ =================
SETTINGS_FILE = "settings.ini"
CACHE_FILE_STD = "cache.json"      
CACHE_FILE_AI = "ai_cache.json"    
DICT_FILE = "dictionary.json"
KOBOLD_API = "http://localhost:5001/v1/chat/completions"

# ================= БРОНЕБОЙНЫЙ МЕНЕДЖЕР НАСТРОЕК =================
class ConfigManager:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.load()

    def load(self):
        self.config.read(SETTINGS_FILE, encoding="utf-8")
        
        defaults = {
            "GENERAL": {
                "mc_dir": os.getcwd(),
                "theme": "Dark",
                "color": "blue",
                "smart_glue": "True",
                "google_workers": "5"
            },
            "AI": {
                "exe_path": "koboldcpp.exe",
                "model_path": "",
                "gpu_layers": "99"
            },
            "API": {
                "deepl_key": ""
            }
        }
        
        changes = False
        for sec, keys in defaults.items():
            if not self.config.has_section(sec):
                self.config.add_section(sec)
                changes = True
            for k, v in keys.items():
                if not self.config.has_option(sec, k):
                    self.config.set(sec, k, str(v))
                    changes = True
                    
        if changes:
            self.save()

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            self.config.write(f)

    def get(self, section, key):
        return self.config.get(section, key)

    def set(self, section, key, value):
        self.config.set(section, key, str(value))
        self.save()

    def getboolean(self, section, key):
        return self.config.getboolean(section, key)

cfg = ConfigManager()
ctk.set_appearance_mode(cfg.get("GENERAL", "theme"))
ctk.set_default_color_theme(cfg.get("GENERAL", "color"))

# ================= УМНЫЙ СКЛЕЙЩИК =================
def apply_smart_glue(text):
    if not text:
        return text
    return re.sub(r'(?<![.!?>\]:])\s*(?:\\n|\r?\n)\s*(?!(?:[\r\n\-*#<]|$|---|[\w\s]+:))', ' ', text)

# ================= ТИТАНОВЫЙ ЩИТ =================
FORMAT_PATTERN = re.compile(
    r'('
    r'\$\([^)]+\)|'                 
    r'[&§][0-9a-fk-orlmn]|'         
    r'<[^>]+>|'                     
    r'\{[^\}]+\}|'                  
    r'\]\([^)]+\)|'                 
    r'!\[[^\]]*\]|'                 
    r'\[[a-z0-9_.-]+:[a-z0-9_./-]+\]|' 
    r'\([a-z0-9_.-]+:[a-z0-9_./-]+\)|' 
    r'\([A-Za-z0-9_./-]+\.md[#a-zA-Z0-9_-]*\)|' 
    r'\n|'                          
    r'%[0-9.,]*\$?[a-zA-Z%]'        
    r')', flags=re.IGNORECASE
)

KEYS_TO_TRANSLATE = {"name", "title", "text", "description", "subtitle", "label", "hover_text", "link_text"}
IGNORE_TERMS = ["RF", "FE", "EU", "J", "mB", "mB/t", "RF/t", "FE/t", "AE", "kW", "kRF", "mB/tick", "ticks", "GUI", "UI", "HUD", "JEI", "REI", "EMI", "API", "JSON", "NBT", "FPS", "TPS", "HP", "XP", "MP", "XP/t", "XYZ", "RGB", "ID", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII"]
IGNORE_TERMS.sort(key=len, reverse=True)
IGNORE_PATTERN = re.compile(r'(?<![a-zA-Z])(' + '|'.join([re.escape(t) for t in IGNORE_TERMS]) + r')(?![a-zA-Z])')

def load_dictionary():
    if not os.path.exists(DICT_FILE):
        default_dict = {"полуслой": "плита", "сыромятная медь": "сырая медь"}
        with open(DICT_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_dict, f, ensure_ascii=False, indent=4)
        return default_dict
    try:
        with open(DICT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

TERMINOLOGY_FIXES = load_dictionary()

def polish_translation(text):
    if not isinstance(text, str) or not text:
        return text
    text = re.sub(r'([&§][0-9a-fk-or])\s+', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+([&§][r])', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\[\s+(%\d*\$?[sd])\s+\]', r'[\1]', text)
    text = re.sub(r'\(\s+(%\d*\$?[sd])\s+\)', r'(\1)', text)
    text = re.sub(r'\"\s+(%\d*\$?[sd])\s+\"', r'"\1"', text)
    text = re.sub(r'%\s+([sd])', r'%\1', text)
    text = re.sub(r'%\s+(\d+)\s*\$\s*([sd])', r'%\1$\2', text)
    text = re.sub(r'%\s*\.\s*(\d+)\s*([fd])', r'%.\1\2', text)
    text = re.sub(r'\]\s+\(', '](', text)
    text = re.sub(r'!\s+\[', '![', text)
    text = re.sub(r'\[\s+', '[', text)
    text = re.sub(r'\s+\]', ']', text)
    text = re.sub(r' {2,}', ' ', text)
    
    for wrong, right in TERMINOLOGY_FIXES.items():
        def repl(match):
            word = match.group(0)
            if word.istitle():
                return right.capitalize()
            elif word.isupper():
                return right.upper()
            return right
        text = re.sub(r'\b' + wrong + r'\b', repl, text, flags=re.IGNORECASE)
    return text

def save_cache_data(cache_data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)

def load_and_polish_cache(filepath):
    cache_data = {}
    changes = 0
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            for k, v in list(cache_data.items()):
                new_v = polish_translation(v)
                if new_v != v:
                    cache_data[k] = new_v
                    changes += 1
            if changes > 0:
                save_cache_data(cache_data, filepath)
        except:
            cache_data = {}
    return cache_data, changes

LANGUAGES = {
    "Русский": {"file": "ru_ru", "api": "ru", "deepl": "RU", "name": "Russian", "regex": r'[А-Яа-яЁё]'},
    "English (UK)": {"file": "en_gb", "api": "en", "deepl": "EN-GB", "name": "English", "regex": r'[a-zA-Z]'},
    "Español": {"file": "es_es", "api": "es", "deepl": "ES", "name": "Spanish", "regex": r'[áéíóúüñÁÉÍÓÚÜÑ]'},
    "Deutsch": {"file": "de_de", "api": "de", "deepl": "DE", "name": "German", "regex": r'[äöüßÄÖÜẞ]'},
    "Français": {"file": "fr_fr", "api": "fr", "deepl": "FR", "name": "French", "regex": r'[àâæçéèêëîïôœùûüÿÀÂÆÇÉÈÊËÎÏÔŒÙÛÜŸ]'},
    "中文 (Упрощ.)": {"file": "zh_cn", "api": "zh-CN", "deepl": "ZH", "name": "Simplified Chinese", "regex": r'[\u4e00-\u9fff]'}
}

def get_mod_name(filepath):
    return os.path.basename(filepath).replace('.jar', '').split('-0')[0].split('-1')[0].replace('_', ' ').title()

def is_translation_key(text):
    return bool(re.match(r'^[a-zA-Z0-9_-]+[.:][a-zA-Z0-9_.-]+$', text.strip()))

def load_lenient_json(raw_bytes):
    text = raw_bytes.decode('utf-8-sig', errors='ignore')
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'(?m)^\s*//.*$', '', text)
    text = re.sub(r',\s*([\]}])', r'\1', text)
    return json.loads(text, strict=False)

def extract_book_strings(data):
    strings = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in KEYS_TO_TRANSLATE and isinstance(v, str):
                strings.append(v)
            elif k in KEYS_TO_TRANSLATE and isinstance(v, list) and all(isinstance(i, str) for i in v):
                strings.extend(v)
            elif isinstance(v, (dict, list)):
                strings.extend(extract_book_strings(v))
    elif isinstance(data, list):
        for item in data:
            strings.extend(extract_book_strings(item))
    return strings

def inject_book_strings(data, t_iter):
    if isinstance(data, dict):
        for k, v in data.items():
            if k in KEYS_TO_TRANSLATE and isinstance(v, str):
                data[k] = next(t_iter)
            elif k in KEYS_TO_TRANSLATE and isinstance(v, list) and all(isinstance(i, str) for i in v):
                data[k] = [next(t_iter) for _ in v]
            elif isinstance(v, (dict, list)):
                inject_book_strings(v, t_iter)
    elif isinstance(data, list):
        for item in data:
            inject_book_strings(item, t_iter)

@lru_cache(maxsize=10000)
def is_technical_term(text):
    if not text:
        return True
    lower = text.lower()
    if not re.search(r'[a-z]', lower):
        return True 
    if re.match(r'^[a-z0-9_.-]+$', lower) and any(c in lower for c in '._'):
        return True
    if any(prefix in lower for prefix in ['glyph_', 'ritual_', 'familiar_', 'source_', 'mana_', 'spell_', 'effect_', 'rune_', 'altar_', 'botania_', 'create_', 'kubejs_']):
        return True
    return False

# ================= ОКНО НАСТРОЕК =================
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("⚙ Настройки MineAI")
        self.geometry("500x550")
        self.resizable(False, False)
        self.grab_set() 

        tabview = ctk.CTkTabview(self)
        tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        tab_ai = tabview.add("Нейросеть (AI)")
        tab_gen = tabview.add("Общие и API")

        # --- TAB: AI ---
        ctk.CTkLabel(tab_ai, text="Исполняемый файл ИИ (.exe):", font=("", 12, "bold")).pack(anchor="w", pady=(10,0), padx=10)
        
        self.ent_ai_exe = ctk.CTkEntry(tab_ai, width=350)
        self.ent_ai_exe.insert(0, cfg.get("AI", "exe_path"))
        self.ent_ai_exe.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(tab_ai, text="Обзор", command=lambda: self.browse(self.ent_ai_exe, [("Executables", "*.exe")]), width=80).pack(anchor="e", padx=10)

        ctk.CTkLabel(tab_ai, text="Языковая модель (.gguf):", font=("", 12, "bold")).pack(anchor="w", pady=(10,0), padx=10)
        
        self.ent_ai_mod = ctk.CTkEntry(tab_ai, width=350)
        self.ent_ai_mod.insert(0, cfg.get("AI", "model_path"))
        self.ent_ai_mod.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(tab_ai, text="Обзор", command=lambda: self.browse(self.ent_ai_mod, [("GGUF Models", "*.gguf")]), width=80).pack(anchor="e", padx=10)

        gpu_val_str = cfg.get("AI", "gpu_layers")
        gpu_val = int(gpu_val_str) if gpu_val_str.isdigit() else 99
        
        self.lbl_gpu = ctk.CTkLabel(tab_ai, text=f"Нагрузка GPU (Слои): {gpu_val}", font=("", 12, "bold"))
        self.lbl_gpu.pack(anchor="w", pady=(10,0), padx=10)
        
        self.slider_gpu = ctk.CTkSlider(tab_ai, from_=0, to=99, number_of_steps=99, command=lambda v: self.lbl_gpu.configure(text=f"Нагрузка GPU (Слои): {int(v)}"))
        self.slider_gpu.set(gpu_val)
        self.slider_gpu.pack(fill="x", padx=10, pady=5)

        # --- TAB: ОБЩИЕ ---
        self.var_smart = ctk.BooleanVar(value=cfg.getboolean("GENERAL", "smart_glue"))
        ctk.CTkSwitch(tab_gen, text="✨ Умный склейщик предложений", variable=self.var_smart).pack(anchor="w", padx=10, pady=15)

        workers_str = cfg.get("GENERAL", "google_workers")
        workers_val = int(workers_str) if workers_str.isdigit() else 5
        
        ctk.CTkLabel(tab_gen, text="Потоки Google Translate:", font=("", 12, "bold")).pack(anchor="w", padx=10)
        
        self.slider_thr = ctk.CTkSlider(tab_gen, from_=1, to=10, number_of_steps=9)
        self.slider_thr.set(workers_val)
        self.slider_thr.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(tab_gen, text="API Ключ DeepL:", font=("", 12, "bold")).pack(anchor="w", pady=(10,0), padx=10)
        
        self.ent_deepl = ctk.CTkEntry(tab_gen, show="*")
        self.ent_deepl.insert(0, cfg.get("API", "deepl_key"))
        self.ent_deepl.pack(fill="x", padx=10, pady=5)

        ctk.CTkButton(self, text="💾 Сохранить настройки", fg_color="#28a745", hover_color="#218838", command=self.save).pack(fill="x", padx=20, pady=10)

    def browse(self, ent, ftypes):
        f = filedialog.askopenfilename(filetypes=ftypes)
        if f:
            ent.delete(0, "end")
            ent.insert(0, f)

    def save(self):
        cfg.set("AI", "exe_path", self.ent_ai_exe.get())
        cfg.set("AI", "model_path", self.ent_ai_mod.get())
        cfg.set("AI", "gpu_layers", int(self.slider_gpu.get()))
        cfg.set("GENERAL", "smart_glue", self.var_smart.get())
        cfg.set("GENERAL", "google_workers", int(self.slider_thr.get()))
        cfg.set("API", "deepl_key", self.ent_deepl.get())
        self.parent.update_ui_from_settings()
        self.destroy()

# ================= ГЛАВНОЕ ПРИЛОЖЕНИЕ =================
class TranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MineAI Translator (V8.4 Locale Scanner)")
        self.geometry("1150x850")
        
        if os.path.exists("icon.ico"):
            try:
                self.iconbitmap("icon.ico")
            except:
                pass
                
        self.ai_process = None
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.total_strings = 0
        self.translated_strings = 0
        self.last_eta_update = 0
        self.auto_scroll = True
        
        self.cache_std, changes_std = load_and_polish_cache(CACHE_FILE_STD)
        self.cache_ai, changes_ai = load_and_polish_cache(CACHE_FILE_AI)
        self.active_cache = self.cache_std
        self.active_cache_file = CACHE_FILE_STD

        self.build_ui()
        self.update_ui_from_settings()
        
        if changes_std + changes_ai > 0:
            self.log_colored(f"✨ Кэш отполирован: исправлено {changes_std + changes_ai} строк.", "magenta")

    def build_ui(self):
        self.frame_left = ctk.CTkScrollableFrame(self, width=370)
        self.frame_left.pack(side="left", fill="y", padx=10, pady=10)
        
        ctk.CTkButton(self.frame_left, text="⚙ НАСТРОЙКИ", fg_color="#555", command=lambda: SettingsWindow(self)).pack(fill="x", padx=10, pady=(0, 15))
        
        ctk.CTkLabel(self.frame_left, text="ПАПКА MINECRAFT", font=("", 14, "bold")).pack(pady=(5, 5))
        self.lbl_folder = ctk.CTkLabel(self.frame_left, text="Не выбрана", text_color="gray")
        self.lbl_folder.pack()
        
        ctk.CTkButton(self.frame_left, text="📁 Выбрать папку", command=self.select_folder, fg_color="#444").pack(pady=5, fill="x", padx=20)

        ctk.CTkLabel(self.frame_left, text="ЦЕЛЕВОЙ ЯЗЫК", font=("", 14, "bold")).pack(pady=(15, 5))
        self.var_lang = ctk.StringVar(value="Русский")
        ctk.CTkOptionMenu(self.frame_left, variable=self.var_lang, values=list(LANGUAGES.keys())).pack(fill="x", padx=20)

        ctk.CTkLabel(self.frame_left, text="МЕТОД СОХРАНЕНИЯ", font=("", 14, "bold")).pack(pady=(15, 5))
        self.var_output = ctk.StringVar(value="resourcepack")
        
        ctk.CTkRadioButton(self.frame_left, text="📦 Создать Resource Pack + Datapack\n(Авто-установка в нужные папки)", variable=self.var_output, value="resourcepack", command=self.update_output_ui).pack(anchor="w", padx=20, pady=5)
        self.entry_rp_name = ctk.CTkEntry(self.frame_left, placeholder_text="Название файлов .zip...")
        self.entry_rp_name.insert(0, "MineAI_Pack")
        self.entry_rp_name.pack(fill="x", padx=40, pady=(0, 5))
        
        ctk.CTkRadioButton(self.frame_left, text="⚠️ Перезаписать .jar", variable=self.var_output, value="inplace", command=self.update_output_ui).pack(anchor="w", padx=20, pady=5)

        ctk.CTkLabel(self.frame_left, text="ЧТО ПЕРЕВОДИМ?", font=("", 14, "bold")).pack(pady=(15, 5))
        self.var_mods = ctk.BooleanVar(value=True)
        self.var_books = ctk.BooleanVar(value=True)
        self.var_quests = ctk.BooleanVar(value=True)
        
        ctk.CTkCheckBox(self.frame_left, text="Интерфейс (Моды)", variable=self.var_mods).pack(anchor="w", padx=20, pady=2)
        ctk.CTkCheckBox(self.frame_left, text="Справочники и Исследования", variable=self.var_books).pack(anchor="w", padx=20, pady=2)
        ctk.CTkCheckBox(self.frame_left, text="Квесты (FTB Quests + Скрипты KubeJS)", variable=self.var_quests).pack(anchor="w", padx=20, pady=2)

        ctk.CTkLabel(self.frame_left, text="ДВИЖОК ПЕРЕВОДА", font=("", 14, "bold")).pack(pady=(15, 5))
        self.var_engine = ctk.StringVar(value="google")
        
        ctk.CTkRadioButton(self.frame_left, text="Google Translate", variable=self.var_engine, value="google", command=self.update_engine_ui).pack(anchor="w", padx=20, pady=5)
        self.frame_google = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        self.var_google_mode = ctk.StringVar(value="single")
        ctk.CTkRadioButton(self.frame_google, text="Построчно (Точно)", variable=self.var_google_mode, value="single").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(self.frame_google, text="Пачками (Быстро)", variable=self.var_google_mode, value="batch").pack(anchor="w", pady=2)
        
        ctk.CTkRadioButton(self.frame_left, text="DeepL API", variable=self.var_engine, value="deepl", command=self.update_engine_ui).pack(anchor="w", padx=20, pady=5)
        
        ctk.CTkRadioButton(self.frame_left, text="Нейросеть (Local AI)", variable=self.var_engine, value="ai", command=self.update_engine_ui).pack(anchor="w", padx=20, pady=5)
        self.frame_ai = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        self.var_ai_mode = ctk.StringVar(value="safe")
        ctk.CTkRadioButton(self.frame_ai, text="Безопасный (По 20 строк)", variable=self.var_ai_mode, value="safe").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(self.frame_ai, text="Контекст + Лор (По 40 строк)", variable=self.var_ai_mode, value="context").pack(anchor="w", pady=2)

        ctk.CTkLabel(self.frame_left, text="РЕЖИМ ОБРАБОТКИ", font=("", 14, "bold")).pack(pady=(15, 5))
        self.var_mode = ctk.StringVar(value="append")
        ctk.CTkRadioButton(self.frame_left, text="Доперевод (Сохранить старое)", variable=self.var_mode, value="append").pack(anchor="w", padx=20, pady=2)
        ctk.CTkRadioButton(self.frame_left, text="Пропуск (От 90%)", variable=self.var_mode, value="skip").pack(anchor="w", padx=20, pady=2)
        ctk.CTkRadioButton(self.frame_left, text="С нуля (Перезапись)", variable=self.var_mode, value="force").pack(anchor="w", padx=20, pady=2)

        self.btn_analyze = ctk.CTkButton(self.frame_left, text="Анализ сборки", fg_color="#0066cc", hover_color="#004c99", command=self.start_analysis)
        self.btn_analyze.pack(pady=(20, 10), fill="x", padx=20)
        
        self.btn_start = ctk.CTkButton(self.frame_left, text="▶ НАЧАТЬ ПЕРЕВОД", fg_color="#28a745", hover_color="#218838", height=40, font=("", 14, "bold"), command=self.start_translation)
        self.btn_start.pack(pady=5, fill="x", padx=20)
        
        self.btn_pause = ctk.CTkButton(self.frame_left, text="⏸ ПАУЗА", fg_color="#ffc107", text_color="black", hover_color="#e0a800", height=40, command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(pady=5, fill="x", padx=20)
        
        self.btn_stop = ctk.CTkButton(self.frame_left, text="⏹ ОСТАНОВИТЬ", fg_color="#dc3545", hover_color="#c82333", height=40, command=self.stop_process, state="disabled")
        self.btn_stop.pack(pady=(5, 10), fill="x", padx=20)

        self.frame_right = ctk.CTkFrame(self)
        self.frame_right.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        self.textbox = ctk.CTkTextbox(self.frame_right, state="disabled", font=("Consolas", 14, "bold"))
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)
        
        tags_colors = [("green", "#2ecc71"), ("yellow", "#f1c40f"), ("red", "#e74c3c"), ("cyan", "#00e5ff"), ("magenta", "#b000ff"), ("dim", "#888888"), ("white", "#ffffff")]
        for tag, color in tags_colors:
            self.textbox.tag_config(tag, foreground=color)
            
        self.textbox.bind("<Button-1>", self.on_user_interaction)
        self.textbox.bind("<Key>", self.on_user_interaction)
        self.textbox.bind("<MouseWheel>", self.on_user_interaction)
        
        self.progress_bar = ctk.CTkProgressBar(self.frame_right)
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self.progress_bar.set(0)
        
        self.lbl_status = ctk.CTkLabel(self.frame_right, text="Ожидание...", font=("", 14))
        self.lbl_status.pack(pady=(0, 10))

        self.update_engine_ui()
        self.update_output_ui()

    def update_ui_from_settings(self):
        f = cfg.get("GENERAL", "mc_dir")
        self.lbl_folder.configure(text=f"...{f[-25:]}" if len(f) > 25 else f)

    def select_folder(self):
        f = filedialog.askdirectory()
        if f:
            cfg.set("GENERAL", "mc_dir", f)
            self.update_ui_from_settings()

    def wait_if_paused(self):
        while self.is_paused and self.is_running:
            time.sleep(0.5)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="▶ ПРОДОЛЖИТЬ", fg_color="#17a2b8", text_color="white")
            self.log_colored("⏸ Процесс поставлен на паузу...", "yellow")
        else:
            self.btn_pause.configure(text="⏸ ПАУЗА", fg_color="#ffc107", text_color="black")
            self.log_colored("▶ Процесс возобновлен...", "green")

    def update_output_ui(self):
        if self.var_output.get() == "resourcepack":
            self.entry_rp_name.configure(state="normal")
        else:
            self.entry_rp_name.configure(state="disabled")

    def update_engine_ui(self):
        self.frame_ai.pack_forget()
        self.frame_google.pack_forget()
        if self.var_engine.get() == "ai":
            self.frame_ai.pack(fill="x", padx=40, pady=5)
        elif self.var_engine.get() == "google":
            self.frame_google.pack(fill="x", padx=40, pady=0)

    def on_user_interaction(self, event=None):
        self.auto_scroll = (self.textbox.yview()[1] >= 0.99)

    def log_colored(self, message, color_tag="white"):
        self.textbox.configure(state="normal")
        at_bottom = self.textbox.yview()[1] >= 0.99
        self.textbox.insert("end", message + "\n", color_tag)
        if self.auto_scroll or at_bottom:
            self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def log_table_row(self, icon, name, m_type, trans_c, en_c, pct):
        self.textbox.configure(state="normal")
        at_bottom = self.textbox.yview()[1] >= 0.99
        self.textbox.insert("end", f"{icon} {name[:34]:<35}", "cyan")
        self.textbox.insert("end", f"[{m_type}]".ljust(15), "magenta")
        self.textbox.insert("end", f"{trans_c}/{en_c}".ljust(12), "white")
        
        color = "green" if pct >= 90 else ("yellow" if pct >= 50 else "red")
        self.textbox.insert("end", f"{pct}%\n", color)
        
        if self.auto_scroll or at_bottom:
            self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def set_status(self, text, val=None):
        if val is not None:
            self.progress_bar.set(val)
        self.lbl_status.configure(text=text)

    def update_eta(self):
        if not self.start_time or self.translated_strings == 0:
            return "расчёт..."
        el = time.time() - self.start_time
        if el < 5:
            return "расчёт..."
        rem = self.total_strings - self.translated_strings
        if rem <= 0:
            return "готово"
        
        sec = rem / (self.translated_strings / el)
        if sec < 60:
            return f"≈ {int(sec)} сек"
        elif sec < 3600:
            return f"≈ {int(sec//60)} мин {int(sec%60)} сек"
        else:
            return f"≈ {int(sec//3600)} ч {int((sec%3600)//60)} мин"

    def lock_ui(self, lock=True):
        state = "disabled" if lock else "normal"
        rev_state = "normal" if lock else "disabled"
        
        self.btn_analyze.configure(state=state)
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state=rev_state)
        self.btn_pause.configure(state=rev_state)

    def stop_process(self):
        self.is_running = False
        self.is_paused = False
        self.set_status("🛑 Остановка...", 1.0)
        self.btn_stop.configure(state="disabled")
        self.btn_pause.configure(state="disabled")
        if self.ai_process:
            try:
                self.ai_process.terminate()
            except:
                pass

    def start_analysis(self):
        self.lock_ui(True)
        self.is_running = True
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        threading.Thread(target=self.run_analysis, daemon=True).start()

    def run_analysis(self):
        mc_dir = cfg.get("GENERAL", "mc_dir")
        l_set = LANGUAGES[self.var_lang.get()]
        t_file = f"{l_set['file']}.json"
        l_reg = l_set.get('regex', r'[А-Яа-яЁё]')
        
        m_dir = os.path.join(mc_dir, "mods")
        q_dir = os.path.join(mc_dir, "config", "ftbquests", "quests")
        
        self.log_colored(f"🚀 Сканирование сборки ({l_set['name']})...\n", "yellow")
        self.log_colored(f"{'ФАЙЛ / МОД':<37}{'ТИП':<15}{'СТРОКИ':<12}ПРОГРЕСС", "white")
        self.log_colored("-" * 75, "dim")
        
        tot_en = 0
        tot_tr = 0
        
        j_files = []
        if os.path.exists(m_dir) and (self.var_mods.get() or self.var_books.get()):
            j_files = [os.path.join(m_dir, f) for f in os.listdir(m_dir) if f.endswith('.jar')]

        for i, fp in enumerate(j_files):
            if not self.is_running:
                break
            self.wait_if_paused()
            
            m_name = get_mod_name(fp)
            self.set_status(f"Анализ: {m_name}...", i / (len(j_files) + 1))
            
            try:
                with zipfile.ZipFile(fp, 'r') as zin:
                    t_files = {item.filename.lower(): item for item in zin.infolist() if t_file in item.filename.lower() or f"/{l_set['file']}/" in item.filename.lower()}
                    
                    if self.var_mods.get():
                        en_c = 0
                        tr_c = 0
                        for item in zin.infolist():
                            if item.filename.lower().endswith('en_us.json') and not any(x in item.filename.lower() for x in ('patchouli', 'lexicon', 'guide')):
                                try:
                                    en_d = load_lenient_json(zin.read(item))
                                    tr_t = item.filename.lower().replace('en_us.json', t_file)
                                    tr_d = load_lenient_json(zin.read(t_files[tr_t])) if tr_t in t_files else {}
                                    
                                    en_c += len([k for k, v in en_d.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v)])
                                    tr_c += sum(1 for k, v in en_d.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v) and (str(tr_d.get(k,"")) != v and str(tr_d.get(k,"")).strip() != ""))
                                except:
                                    pass
                        if en_c > 0:
                            tot_en += en_c
                            tot_tr += tr_c
                            self.log_table_row("📦", m_name, "Интерфейс", tr_c, en_c, int(tr_c/en_c*100))

                    if self.var_books.get():
                        b_en = 0
                        b_tr = 0
                        m_en = 0
                        m_tr = 0
                        
                        for item in zin.infolist():
                            fl = item.filename.lower()
                            is_jb = fl.endswith('.json') and (('/en_us/' in fl and any(x in fl for x in ('patchouli', 'lexicon', 'guide'))) or '/research/' in fl or '/researches/' in fl or '/quests/' in fl)
                            is_mb = (fl.endswith('.md') or fl.endswith('.txt')) and any(x in fl for x in ('/en_us/', '/ae2guide/', '/guide/', '/manual/', '/lexicon/'))
                            
                            if is_jb:
                                try:
                                    en_d = load_lenient_json(zin.read(item))
                                    tr_t = fl.replace('/en_us/', f"/{l_set['file']}/")
                                    tr_d = load_lenient_json(zin.read(t_files[tr_t])) if tr_t in t_files else {}
                                    
                                    en_s = [s for s in extract_book_strings(en_d) if s.strip() and re.search(r'[a-zA-Z]', s)]
                                    tr_s = [s for s in extract_book_strings(tr_d) if s.strip()] if tr_d else []
                                    
                                    b_en += len(en_s)
                                    b_tr += sum(1 for idx, s in enumerate(en_s) if idx < len(tr_s) and tr_s[idx] != s)
                                except:
                                    pass
                                    
                            elif is_mb:
                                try:
                                    en_t = zin.read(item).decode('utf-8-sig', errors='ignore')
                                    tr_t = fl.replace('/en_us/', f"/{l_set['file']}/") if '/en_us/' in fl else fl
                                    tr_text = zin.read(t_files[tr_t]).decode('utf-8-sig', errors='ignore') if tr_t in t_files else ""
                                    
                                    in_y = False
                                    for idx, s in enumerate(en_t.split('\n')):
                                        if s.strip() == '---':
                                            in_y = not in_y
                                            continue
                                        if in_y:
                                            if s.strip().lower().startswith('title:'):
                                                m = re.match(r'^(\s*title\s*:\s*[\'"]?)(.*?)([\'"]?)$', s, re.IGNORECASE)
                                                if m and re.search(r'[a-zA-Z]', m.group(2)):
                                                    m_en += 1
                                                    if idx < len(tr_text.split('\n')) and re.search(l_reg, tr_text.split('\n')[idx]):
                                                        m_tr += 1
                                            continue
                                            
                                        if s.strip().startswith('<') or s.strip().startswith('!['):
                                            continue
                                        if s.strip() and re.search(r'[a-zA-Z]', s) and not is_technical_term(s):
                                            m_en += 1
                                            if idx < len(tr_text.split('\n')) and re.search(l_reg, tr_text.split('\n')[idx]):
                                                m_tr += 1
                                except:
                                    pass
                                    
                        if b_en > 0:
                            tot_en += b_en
                            tot_tr += b_tr
                            self.log_table_row("📖", m_name, "Книга(JSON)", b_tr, b_en, int(b_tr/b_en*100))
                        if m_en > 0:
                            tot_en += m_en
                            tot_tr += m_tr
                            self.log_table_row("📝", m_name, "Книга(MD)", m_tr, m_en, int(m_tr/m_en*100))
            except:
                pass

        # Ищем внешние словари (Локализация скриптов и квестов)
        loose_lang_files = []
        if self.var_quests.get() or self.var_mods.get():
            search_dirs = ["kubejs/assets", "defaultconfigs", "config/ftbquests/lang"]
            for d in search_dirs:
                p = os.path.join(mc_dir, d.replace("/", os.sep))
                if os.path.exists(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.lower() == 'en_us.json':
                                loose_lang_files.append(os.path.join(root, f))
                                
        for i, fp in enumerate(loose_lang_files):
            if not self.is_running: break
            self.wait_if_paused()
            
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    en_d = load_lenient_json(f.read().encode('utf-8'))
                tr_d = {}
                tr_disk_path = fp.replace('en_us.json', f"{l_set['file']}.json")
                if os.path.exists(tr_disk_path):
                    with open(tr_disk_path, 'r', encoding='utf-8') as f:
                        tr_d = load_lenient_json(f.read().encode('utf-8'))
                        
                en_c = len([k for k, v in en_d.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v)])
                tr_c = sum(1 for k, v in en_d.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v) and (str(tr_d.get(k,"")) != v and str(tr_d.get(k,"")).strip() != ""))
                
                if en_c > 0:
                    tot_en += en_c
                    tot_tr += tr_c
                    self.log_table_row("🗂️", f"Словарь: {os.path.basename(os.path.dirname(os.path.dirname(fp)))}", "Локализация", tr_c, en_c, int(tr_c/en_c*100))
            except: pass

        s_files = []
        if os.path.exists(q_dir) and self.var_quests.get():
            for root, _, files in os.walk(q_dir):
                s_files.extend([os.path.join(root, f) for f in files if f.endswith('.snbt')])
                
        for i, fp in enumerate(s_files):
            if not self.is_running:
                break
            self.wait_if_paused()
            self.set_status(f"Анализ: {os.path.basename(fp)}...", (len(j_files) + i) / (len(j_files) + len(s_files)))
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    c = f.read()
                    
                strs = []
                for m in re.finditer(r'(?:"|)(?:title|subtitle|text)(?:"|)\s*:\s*"((?:[^"\\]|\\.)*)"', c, re.IGNORECASE):
                    strs.append(m.group(1))
                    
                # Ищем массивы строк (описание и текст задач)
                for m in re.finditer(r'(?:"|)(?:description|text)(?:"|)\s*:\s*\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\]', c, re.IGNORECASE):
                    strs.extend(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(0)))
                    
                v_str = list(set([s for s in strs if s.strip() and not is_translation_key(s) and re.search(r'[a-zA-Z]', s)]))
                en_c = len(v_str)
                tr_c = sum(1 for s in v_str if re.search(l_reg, s))
                
                if en_c > 0:
                    tot_en += en_c
                    tot_tr += tr_c
                    self.log_table_row("📜", os.path.basename(fp), "Квесты", tr_c, en_c, int(tr_c/en_c*100))
            except:
                pass

        self.log_colored("-" * 75, "dim")
        if not self.is_running:
            self.log_colored("🛑 АНАЛИЗ ПРЕРВАН", "red")
        elif tot_en > 0:
            pct = int((tot_tr / tot_en) * 100)
            color = "green" if pct >= 90 else ("yellow" if pct >= 50 else "red")
            self.log_colored(f"✅ АНАЛИЗ ЗАВЕРШЕН! Готовность: {pct}% | Строк: {tot_en}", color)
        else:
            self.log_colored("❌ Нечего переводить!", "red")
            
        self.set_status("Готово", 1.0)
        self.lock_ui(False)

    def start_translation(self):
        if not cfg.get("GENERAL", "mc_dir"):
            messagebox.showerror("Ошибка", "Выберите папку Minecraft!")
            return
            
        self.lock_ui(True)
        self.is_running = True
        self.is_paused = False
        
        self.btn_pause.configure(text="⏸ ПАУЗА", fg_color="#ffc107", text_color="black")
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        
        threading.Thread(target=self._run_translation_wrapper, daemon=True).start()

    def _run_translation_wrapper(self):
        try:
            self.run_translation()
        except Exception as e:
            self.log_colored(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:\n{traceback.format_exc()}", "red")
            self.set_status("Ошибка!")
            self.lock_ui(False)

    def estimate_total_strings(self, j_files, l_files, s_files, l_set, mod_ovr):
        tot = 0
        l_reg = l_set.get('regex', r'[А-Яа-яЁё]')
        t_file = f"{l_set['file']}.json"
        smart = cfg.getboolean("GENERAL", "smart_glue")
        
        for fp in j_files:
            if not self.is_running:
                return tot
            self.wait_if_paused()
            try:
                with zipfile.ZipFile(fp, 'r') as zin:
                    t_files = {i.filename.lower(): i for i in zin.infolist() if t_file in i.filename.lower() or f"/{l_set['file']}/" in i.filename.lower()}
                    for i in zin.infolist():
                        fl = i.filename.lower()
                        is_jb = fl.endswith('.json') and (('/en_us/' in fl and any(x in fl for x in ('patchouli', 'lexicon', 'guide'))) or '/research/' in fl or '/researches/' in fl or '/quests/' in fl)
                        is_mb = (fl.endswith('.md') or fl.endswith('.txt')) and any(x in fl for x in ('/en_us/', '/ae2guide/', '/guide/', '/manual/', '/lexicon/'))
                        is_lang = (fl.endswith('en_us.json') and not is_jb)

                        if self.var_mods.get() and is_lang:
                            try:
                                en_d = load_lenient_json(zin.read(i))
                            except:
                                continue
                            tr_d = load_lenient_json(zin.read(t_files.get(fl.replace('en_us.json', t_file), None))) if fl.replace('en_us.json', t_file) in t_files else {}
                            
                            for k, v in en_d.items():
                                if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v):
                                    if mod_ovr == "force" or not (k in tr_d and isinstance(tr_d[k], str) and tr_d[k].strip()):
                                        tot += 1
                                        
                        elif self.var_books.get() and is_jb:
                            try:
                                en_d = load_lenient_json(zin.read(i))
                                strs = [s for s in extract_book_strings(en_d) if s.strip() and re.search(r'[a-zA-Z]', s) and not is_technical_term(s)]
                                tot += len(strs)
                            except:
                                pass
                                
                        elif self.var_books.get() and is_mb:
                            try:
                                t = zin.read(i).decode('utf-8-sig', errors='ignore')
                                if smart:
                                    t = apply_smart_glue(t)
                                in_y = False
                                for s in t.split('\n'):
                                    s_s = s.strip()
                                    if s_s == '---':
                                        in_y = not in_y
                                        continue
                                    if in_y:
                                        if s_s.lower().startswith('title:') and re.search(r'[a-zA-Z]', s):
                                            tot += 1
                                        continue
                                    if s_s.startswith('<') or s_s.startswith('!['):
                                        continue
                                    if s.strip() and re.search(r'[a-zA-Z]', s) and not is_technical_term(s):
                                        tot += 1
                            except:
                                pass
            except:
                pass
                
        for fp in l_files:
            if not self.is_running: return tot
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    en_d = load_lenient_json(f.read().encode('utf-8'))
                tr_disk_path = fp.replace('en_us.json', t_file)
                tr_d = {}
                if os.path.exists(tr_disk_path):
                    with open(tr_disk_path, 'r', encoding='utf-8') as f:
                        tr_d = load_lenient_json(f.read().encode('utf-8'))
                for k, v in en_d.items():
                    if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v):
                        if mod_ovr == "force" or not (k in tr_d and isinstance(tr_d[k], str) and tr_d[k].strip()):
                            tot += 1
            except: pass
                
        for fp in s_files:
            if not self.is_running:
                return tot
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    c = f.read()
                strs = []
                for m in re.finditer(r'(?:"|)(?:title|subtitle|text)(?:"|)\s*:\s*"((?:[^"\\]|\\.)*)"', c, re.IGNORECASE):
                    strs.append(m.group(1))
                for m in re.finditer(r'(?:"|)(?:description|text)(?:"|)\s*:\s*\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\]', c, re.IGNORECASE):
                    strs.extend(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(0)))
                v = [s for s in strs if s.strip() and not is_translation_key(s) and re.search(r'[a-zA-Z]', s)]
                
                if mod_ovr == "force":
                    tot += len(v)
                else:
                    tot += sum(1 for s in v if not re.search(l_reg, s))
            except:
                pass
                
        return tot

    def run_translation(self):
        eng = self.var_engine.get()
        mc = cfg.get("GENERAL", "mc_dir")
        
        if eng == "ai":
            self.active_cache = self.cache_ai
            self.active_cache_file = CACHE_FILE_AI
        else:
            self.active_cache = self.cache_std
            self.active_cache_file = CACHE_FILE_STD
            
        l_set = LANGUAGES[self.var_lang.get()]
        m_ovr = self.var_mode.get()
        o_mod = self.var_output.get()
        
        m_dir = os.path.join(mc, "mods")
        q_dir = os.path.join(mc, "config", "ftbquests", "quests")
        rp_dir = os.path.join(mc, "resourcepacks")
        dp_dir = os.path.join(mc, "config", "openloader", "data")

        if eng == "deepl" and not cfg.get("API", "deepl_key").strip():
            self.log_colored("❌ Введите ключ DeepL!", "red")
            self.lock_ui(False)
            return
            
        if eng == "ai" and not cfg.get("AI", "model_path"):
            self.log_colored("❌ Выберите модель .gguf!", "red")
            self.lock_ui(False)
            return

        j_files = []
        if os.path.exists(m_dir) and (self.var_mods.get() or self.var_books.get()):
            j_files = [os.path.join(m_dir, f) for f in os.listdir(m_dir) if f.endswith('.jar')]
            
        l_files = []
        if self.var_quests.get() or self.var_mods.get():
            search_dirs = ["kubejs/assets", "defaultconfigs", "config/ftbquests/lang"]
            for d in search_dirs:
                p = os.path.join(mc, d.replace("/", os.sep))
                if os.path.exists(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.lower() == 'en_us.json':
                                l_files.append(os.path.join(root, f))
                                
        s_files = []
        if self.var_quests.get() and os.path.exists(q_dir):
            for r, _, fs in os.walk(q_dir):
                for f in fs:
                    if f.endswith('.snbt'):
                        s_files.append(os.path.join(r, f))
                        
        if len(j_files) + len(s_files) + len(l_files) == 0:
            self.log_colored("❌ Нечего переводить!", "red")
            self.lock_ui(False)
            return

        self.log_colored("📊 Подсчёт строк...", "yellow")
        self.total_strings = self.estimate_total_strings(j_files, l_files, s_files, l_set, m_ovr)
        self.log_colored(f"   Найдено: {self.total_strings}", "cyan")
        
        if eng == "ai" and not self.setup_and_start_ai():
            self.lock_ui(False)
            return

        rp_zip = None
        rp_h = None
        dp_zip = None
        dp_h = None
        w_files = set()
        
        if o_mod == "resourcepack":
            os.makedirs(rp_dir, exist_ok=True)
            b_rp = self.entry_rp_name.get().strip() or f"MineAI_{l_set['name']}"
            b_rp = re.sub(r'[\\/*?:"<>|]', "", b_rp)
            if not b_rp.lower().endswith(".zip"):
                b_rp += ".zip"
                
            r_nm = b_rp
            c = 1
            while True:
                rp_zip = os.path.join(rp_dir, r_nm)
                if os.path.exists(rp_zip):
                    try:
                        os.remove(rp_zip)
                        break
                    except:
                        r_nm = b_rp.replace(".zip", f"_{c}.zip")
                        c += 1
                else:
                    break
                    
            with zipfile.ZipFile(rp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 15, "description": f"{r_nm} - MineAI"}}, indent=2))
            rp_h = zipfile.ZipFile(rp_zip, 'a', compression=zipfile.ZIP_DEFLATED)
            self.log_colored(f"📦 Создан ресурспак: {rp_zip}", "cyan")
            
            os.makedirs(dp_dir, exist_ok=True)
            dp_nm = r_nm.replace(".zip", "_Datapack.zip")
            dp_zip = os.path.join(dp_dir, dp_nm)
            
            if os.path.exists(dp_zip):
                try:
                    os.remove(dp_zip)
                except:
                    pass
                    
            with zipfile.ZipFile(dp_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 15, "description": f"{dp_nm} - MineAI"}}, indent=2))
            dp_h = zipfile.ZipFile(dp_zip, 'a', compression=zipfile.ZIP_DEFLATED)
            self.log_colored(f"📂 Создан Датапак: {dp_zip}", "magenta")

        self.log_colored(f"🚀 ЗАПУСК ПЕРЕВОДА ({l_set['name']})...\n", "yellow")
        
        self.start_time = time.time()
        self.translated_strings = 0
        self.last_eta_update = time.time()
        proc = 0
        total_items = len(j_files) + len(s_files) + len(l_files)
        
        try:
            for fp in j_files:
                if not self.is_running:
                    break
                self.wait_if_paused()
                self.process_jar(fp, eng, m_ovr, o_mod, l_set, rp_h, dp_h, w_files)
                proc += 1
                self.set_status(f"Модов: {proc}/{len(j_files)} | ETA: {self.update_eta()}", proc / total_items)
                
            for fp in l_files:
                if not self.is_running:
                    break
                self.wait_if_paused()
                self.process_loose_json(fp, eng, m_ovr, o_mod, l_set, rp_h, dp_h, w_files)
                proc += 1
                self.set_status(f"Словарей: {proc}/{total_items} | ETA: {self.update_eta()}", proc / total_items)
                
            for fp in s_files:
                if not self.is_running:
                    break
                self.wait_if_paused()
                self.process_snbt(fp, eng, m_ovr, l_set)
                proc += 1
                self.set_status(f"Квестов: {proc}/{total_items} | ETA: {self.update_eta()}", proc / total_items)
                
            save_cache_data(self.active_cache, self.active_cache_file)
            
        finally:
            if rp_h:
                rp_h.close()
            if dp_h:
                dp_h.close()

        if not self.is_running:
            self.log_colored("\n🛑 ОСТАНОВЛЕНО.", "red")
        else:
            self.log_colored("\n✅ ПЕРЕВОД УСПЕШНО ЗАВЕРШЕН!", "green")
            if o_mod == "resourcepack": 
                self.log_colored("💡 Готово! Ресурспак и Датапак разложены по нужным папкам.", "yellow")
                
        self.set_status("Все задачи выполнены!" if self.is_running else "Остановлено", 1.0)
        self.lock_ui(False)

    def setup_and_start_ai(self):
        try:
            if requests.get(KOBOLD_API.replace("chat/completions", "models"), timeout=1).status_code == 200:
                self.log_colored("✅ ИИ уже работает", "green")
                return True
        except:
            pass
            
        ep = cfg.get("AI", "exe_path")
        mp = cfg.get("AI", "model_path")
        
        gpu_str = cfg.get("AI", "gpu_layers")
        g = gpu_str if gpu_str.isdigit() else "99"
        
        self.log_colored(f"🤖 Запуск ИИ...", "cyan")
        try:
            self.ai_process = subprocess.Popen([
                ep, mp, "--port", "5001", "--quiet", "--contextsize", "8192", 
                "--usecublas", "--gpulayers", g
            ], stdout=subprocess.DEVNULL)
        except Exception as e:
            self.log_colored(f"❌ Ошибка ИИ: {e}", "red")
            return False
            
        for i in range(180):
            if not self.is_running:
                return False
            self.set_status(f"Прогрев нейросети... ({i}/180 сек)")
            try:
                if requests.get(KOBOLD_API.replace("chat/completions", "models"), timeout=1).status_code == 200:
                    self.log_colored("✅ ИИ успешно запущен!\n", "green")
                    return True
            except:
                time.sleep(1)
                
        self.log_colored("❌ Сервер ИИ не отвечает.", "red")
        return False

    def translate_engine(self, d_dict, eng, l_set, ctx=""):
        res = {}
        to_tr = {}
        in_c = 0
        smart = cfg.getboolean("GENERAL", "smart_glue")
        
        for k, t in d_dict.items():
            if not self.is_running:
                break
            self.wait_if_paused()
            
            if smart:
                t = apply_smart_glue(t)
                
            ck = f"{l_set['api']}_{t}"
            if ck in self.active_cache:
                res[k] = self.active_cache[ck]
                in_c += 1
                self.translated_strings += 1
                continue
                
            mmap = {}
            def mf(m):
                mk = f" [#{len(mmap)}#] "
                mmap[mk.strip()] = m.group(0)
                return mk
                
            msk = re.sub(r'\s+', ' ', IGNORE_PATTERN.sub(mf, FORMAT_PATTERN.sub(mf, t))).strip()
            
            if not msk:
                res[k] = t
                self.translated_strings += 1
                continue
                
            to_tr[k] = {"original": t, "masked": msk, "mapping": mmap}

        if in_c > 0:
            self.log_colored(f"   🗃️ Из кэша: {in_c} строк", "dim")
            
        if not to_tr or not self.is_running:
            return res

        if eng == "google":
            gm = self.var_google_mode.get() if hasattr(self, 'var_google_mode') else "single"
            
            wk_str = cfg.get("GENERAL", "google_workers")
            wk = int(wk_str) if wk_str.isdigit() else 5
            
            if gm == "batch":
                chks = []
                ck = []
                ct = ""
                for k, v in to_tr.items():
                    if len(ct) + len(v["masked"]) > 2000 or len(ck) >= 20:
                        chks.append((ck, ct))
                        ck = [k]
                        ct = v["masked"]
                    else:
                        ck.append(k)
                        ct = ct + " |~| " + v["masked"] if ct else v["masked"]
                if ck:
                    chks.append((ck, ct))
                    
                def tr_chk(cks, tts):
                    for _ in range(3):
                        if not self.is_running:
                            return cks, None
                        try:
                            r = requests.get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": "en", "tl": l_set['api'], "dt": "t", "q": tts}, timeout=10)
                            if r.status_code == 429:
                                time.sleep(3)
                                continue
                            pts = re.split(r'\s*\|\s*~\s*\|\s*', "".join([p[0] for p in r.json()[0] if p[0]]))
                            if len(pts) == len(cks):
                                return cks, pts
                        except:
                            time.sleep(1)
                    return cks, None
                    
                with ThreadPoolExecutor(max_workers=wk) as ex:
                    for fut in as_completed([ex.submit(tr_chk, c, t) for c, t in chks]):
                        if not self.is_running:
                            break
                        self.wait_if_paused()
                        cks, pts = fut.result()
                        if pts:
                            for idx, k in enumerate(cks):
                                tr = pts[idx].strip()
                                for mi, (m, orig) in enumerate(to_tr[k]["mapping"].items()):
                                    tr = re.sub(rf'\[\s*#\s*{mi}\s*#\s*\]', lambda x, o=orig: o, tr)
                                tr = polish_translation(tr)
                                res[k] = tr
                                self.active_cache[f"{l_set['api']}_{to_tr[k]['original']}"] = tr
                                self.translated_strings += 1
                                self.log_colored(f" > {to_tr[k]['original'][:40]} -> {tr[:40]}", "dim")
                        else:
                            for k in cks:
                                try:
                                    r = requests.get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": "en", "tl": l_set['api'], "dt": "t", "q": to_tr[k]["masked"]}, timeout=5).json()
                                    
                                    def restore_map(m):
                                        idx = int(m.group(1))
                                        return list(to_tr[k]["mapping"].values())[idx]
                                        
                                    raw_text = "".join([p[0] for p in r[0] if p[0]])
                                    tr = polish_translation(re.sub(rf'\[\s*#\s*(\d+)\s*#\s*\]', restore_map, raw_text))
                                    
                                    res[k] = tr
                                    self.active_cache[f"{l_set['api']}_{to_tr[k]['original']}"] = tr
                                    self.log_colored(f" > {to_tr[k]['original'][:40]} -> {tr[:40]}", "dim")
                                except:
                                    res[k] = to_tr[k]["original"]
                                self.translated_strings += 1
                                time.sleep(0.3)
            else:
                def tr_sng(k, tts):
                    for _ in range(3):
                        if not self.is_running:
                            return k, None
                        try:
                            r = requests.get("https://translate.googleapis.com/translate_a/single", params={"client": "gtx", "sl": "en", "tl": l_set['api'], "dt": "t", "q": tts}, timeout=10)
                            if r.status_code == 429:
                                time.sleep(3)
                                continue
                            return k, "".join([p[0] for p in r.json()[0] if p[0]])
                        except:
                            time.sleep(1)
                    return k, None
                    
                with ThreadPoolExecutor(max_workers=wk) as ex:
                    for fut in as_completed([ex.submit(tr_sng, k, v["masked"]) for k, v in to_tr.items()]):
                        if not self.is_running:
                            break
                        self.wait_if_paused()
                        k, tr = fut.result()
                        if tr:
                            for mi, (m, orig) in enumerate(to_tr[k]["mapping"].items()):
                                tr = re.sub(rf'\[\s*#\s*{mi}\s*#\s*\]', lambda x, o=orig: o, tr)
                            tr = polish_translation(tr)
                            res[k] = tr
                            self.active_cache[f"{l_set['api']}_{to_tr[k]['original']}"] = tr
                            self.log_colored(f" > {to_tr[k]['original'][:40]} -> {tr[:40]}", "dim")
                        else:
                            res[k] = to_tr[k]["original"]
                        self.translated_strings += 1

        elif eng == "deepl":
            ak = cfg.get("API", "deepl_key").strip()
            url = "https://api.deepl.com/v2/translate" if not ak.endswith(":fx") else "https://api-free.deepl.com/v2/translate"
            bk = list(to_tr.keys())
            
            for i in range(0, len(bk), 40):
                if not self.is_running:
                    break
                self.wait_if_paused()
                ck = bk[i:i+40]
                try:
                    payload = {
                        "text": [to_tr[k]["masked"] for k in ck],
                        "target_lang": l_set['deepl']
                    }
                    r = requests.post(url, headers={"Authorization": f"DeepL-Auth-Key {ak}"}, json=payload).json()
                    
                    for idx, k in enumerate(ck):
                        tr = r["translations"][idx]["text"]
                        for mi, (m, orig) in enumerate(to_tr[k]["mapping"].items()):
                            tr = re.sub(rf'\[\s*#\s*{mi}\s*#\s*\]', lambda x, o=orig: o, tr)
                        tr = polish_translation(tr)
                        res[k] = tr
                        self.active_cache[f"{l_set['api']}_{to_tr[k]['original']}"] = tr
                        self.translated_strings += 1
                        self.log_colored(f" > {to_tr[k]['original'][:40]} -> {tr[:40]}", "dim")
                except Exception as e:
                    self.log_colored(f"❌ Ошибка DeepL: {e}", "red")
                    for k in ck:
                        res[k] = to_tr[k]["original"]
                time.sleep(0.5)

        else:
            am = self.var_ai_mode.get() if hasattr(self, 'var_ai_mode') else "safe"
            bs = 40 if am == "context" else 20
            mt = 4096 if am == "context" else 2048
            bk = list(to_tr.keys())
            
            def p_ai(ck):
                if not self.is_running:
                    return False
                sd = {k: to_tr[k]["masked"] for k in ck}
                
                if am == "context" and ctx:
                    pm = f"Ты локализатор. Переведи текст мода/квеста '{ctx}' на {l_set['name']}. Адаптируй лор. ПРАВИЛА: Не переводи ключи. Сохраняй [#0#]. Верни ТОЛЬКО валидный JSON. Текст: {json.dumps(sd, ensure_ascii=False)}"
                else:
                    pm = f"Translate the following JSON string values from English to {l_set['name']}. RULES: Do not translate keys. Preserve [#0#] tags exactly. Return ONLY valid JSON. Text: {json.dumps(sd, ensure_ascii=False)}"
                    
                self.set_status(f"⏳ ИИ переводит (пакет {len(ck)} строк)... | ETA: {self.update_eta()}")
                
                try:
                    payload = {"messages": [{"role": "user", "content": pm}], "temperature": 0.1, "max_tokens": mt}
                    r = requests.post(KOBOLD_API, json=payload, timeout=300)
                    
                    clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', r.json()['choices'][0]['message']['content'].strip(), flags=re.IGNORECASE).strip()
                    td = json.loads(clean_json, strict=False)
                    
                    for k in ck:
                        if k in td:
                            tr = td[k]
                            for mi, (m, orig) in enumerate(to_tr[k]["mapping"].items()):
                                tr = re.sub(rf'\[\s*#\s*{mi}\s*#\s*\]', lambda x, o=orig: o, tr)
                            tr = polish_translation(tr)
                            res[k] = tr
                            self.active_cache[f"{l_set['api']}_{to_tr[k]['original']}"] = tr
                            self.translated_strings += 1
                            self.log_colored(f" > {to_tr[k]['original'][:40]} -> {tr[:40]}", "dim")
                        else:
                            res[k] = to_tr[k]["original"]
                            self.translated_strings += 1
                    return True
                except:
                    return False 
                    
            i = 0
            while i < len(bk):
                if not self.is_running:
                    break
                self.wait_if_paused()
                cb = bk[i:i+bs]
                
                if not p_ai(cb) and self.is_running:
                    self.log_colored(f"❌ Ошибка ИИ. Дробим пакет...", "yellow")
                    for j in range(0, len(cb), 10):
                        if not self.is_running:
                            break
                        self.wait_if_paused()
                        sb = cb[j:j+10]
                        if not p_ai(sb) and self.is_running:
                            for k in sb:
                                res[k] = to_tr[k]["original"]
                                self.translated_strings += 1
                i += bs

        if len(self.active_cache) % 500 == 0:
            save_cache_data(self.active_cache, self.active_cache_file)
            
        return res

    def process_loose_json(self, fp, eng, m_ovr, o_mod, l_set, rp_h=None, dp_h=None, w_fs=None):
        if w_fs is None:
            w_fs = set()
            
        mc_dir = cfg.get("GENERAL", "mc_dir")
        
        rel_path = os.path.relpath(fp, mc_dir).replace('\\', '/')
        if 'assets/' in rel_path:
            rp_internal_path = rel_path[rel_path.find('assets/'):]
        else:
            rp_internal_path = "assets/kubejs/lang/" + os.path.basename(fp)
            
        tr_internal_path = rp_internal_path.replace('en_us.json', f"{l_set['file']}.json")
        tr_disk_path = fp.replace('en_us.json', f"{l_set['file']}.json")
        
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                en_d = load_lenient_json(f.read().encode('utf-8'))
                
            tr_d = {}
            if os.path.exists(tr_disk_path):
                with open(tr_disk_path, 'r', encoding='utf-8') as f:
                    tr_d = load_lenient_json(f.read().encode('utf-8'))
                    
            fd = en_d.copy()
            kt = {}
            
            for k, et in en_d.items():
                if not isinstance(et, str) or not et.strip():
                    continue
                if is_technical_term(et):
                    fd[k] = et
                    continue
                if m_ovr == "append" and k in tr_d and isinstance(tr_d[k], str) and tr_d[k].strip():
                    fd[k] = tr_d[k]
                    if fd[k] == et and re.search(r'[a-zA-Z]', et):
                        kt[k] = et
                elif re.search(r'[a-zA-Z]', et):
                    kt[k] = et

            te = len([k for k, v in en_d.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v)])
            
            if te > 0:
                m_nm = "Словарь: " + os.path.basename(os.path.dirname(os.path.dirname(fp)))
                
                if m_ovr == "skip" and (te - len(kt)) >= te * 0.9:
                    if o_mod == "resourcepack" and rp_h and tr_internal_path not in w_fs and os.path.exists(tr_disk_path):
                        with open(tr_disk_path, 'rb') as f:
                            rp_h.writestr(tr_internal_path, f.read())
                        w_fs.add(tr_internal_path)
                elif len(kt) == 0 and m_ovr == "append":
                    if o_mod == "resourcepack" and rp_h and tr_internal_path not in w_fs:
                        rp_h.writestr(tr_internal_path, json.dumps(fd, ensure_ascii=False, indent=2).encode('utf-8'))
                        w_fs.add(tr_internal_path)
                else:
                    self.log_colored(f"⚡ Перевод {m_nm} - {len(kt)} строк", "cyan")
                    td_rt = self.translate_engine(kt, eng, l_set, ctx="Локализация Квестов/Скриптов")
                    for k, v in td_rt.items():
                        fd[k] = v
                        
                    od = json.dumps(fd, ensure_ascii=False, indent=2).encode('utf-8')
                    
                    if o_mod == "resourcepack" and rp_h and tr_internal_path not in w_fs:
                        rp_h.writestr(tr_internal_path, od)
                        w_fs.add(tr_internal_path)
                    elif o_mod == "inplace":
                        with open(tr_disk_path, 'wb') as f:
                            f.write(od)
        except Exception as e:
            self.log_colored(f"❌ Ошибка словаря локализации {fp}: {e}", "red")

    def process_jar(self, fp, eng, m_ovr, o_mod, l_set, rp_h=None, dp_h=None, w_fs=None):
        if w_fs is None:
            w_fs = set()
            
        if not self.var_mods.get() and not self.var_books.get():
            return
            
        m_nm = get_mod_name(fp)
        tf = f"{l_set['file']}.json"
        tmp = fp + ".temp"
        t_any = False
        
        try:
            with zipfile.ZipFile(fp, 'r') as zin:
                zout = zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) if o_mod == "inplace" else None
                try:
                    ru_w = set()
                    t_fs = {i.filename.lower(): i for i in zin.infolist() if tf in i.filename.lower() or f"/{l_set['file']}/" in i.filename.lower()}
                    
                    for i in zin.infolist():
                        if not self.is_running:
                            break
                        self.wait_if_paused()
                        
                        fl = i.filename.lower()
                        is_jb = fl.endswith('.json') and (('/en_us/' in fl and any(x in fl for x in ('patchouli', 'lexicon', 'guide'))) or '/research/' in fl or '/researches/' in fl or '/quests/' in fl)
                        is_mb = (fl.endswith('.md') or fl.endswith('.txt')) and any(x in fl for x in ('/en_us/', '/ae2guide/', '/guide/', '/manual/', '/lexicon/'))
                        is_lg = (fl.endswith('en_us.json') and not is_jb)
                        
                        if o_mod == "inplace" and tf not in fl and f"/{l_set['file']}/" not in fl:
                            zout.writestr(i, zin.read(i))

                        if self.var_mods.get() and is_lg:
                            trn = re.sub(r'en_us\.json$', tf, i.filename, flags=re.IGNORECASE)
                            trt = trn.lower()
                            ah = dp_h if fl.startswith('data/') else rp_h
                            
                            try:
                                ed = load_lenient_json(zin.read(i))
                            except:
                                continue
                                
                            td = load_lenient_json(zin.read(t_fs[trt])) if trt in t_fs else {}
                            fd = ed.copy()
                            kt = {}
                            
                            for k, et in ed.items():
                                if not isinstance(et, str) or not et.strip():
                                    continue
                                if is_technical_term(et):
                                    fd[k] = et
                                    continue
                                if m_ovr == "append" and k in td and isinstance(td[k], str) and td[k].strip():
                                    fd[k] = td[k]
                                    if fd[k] == et and re.search(r'[a-zA-Z]', et):
                                        kt[k] = et
                                elif re.search(r'[a-zA-Z]', et):
                                    kt[k] = et
                                    
                            te = len([k for k, v in ed.items() if isinstance(v, str) and re.search(r'[a-zA-Z]', v) and not is_technical_term(v)])
                            
                            if te > 0:
                                if m_ovr == "skip" and (te - len(kt)) >= te * 0.9:
                                    if o_mod == "resourcepack" and trt in t_fs and ah and trn not in w_fs:
                                        ah.writestr(trn, zin.read(t_fs[trt]))
                                        w_fs.add(trn)
                                elif len(kt) == 0 and m_ovr == "append":
                                    if o_mod == "resourcepack" and ah and trn not in w_fs:
                                        ah.writestr(trn, json.dumps(fd, ensure_ascii=False, indent=2).encode('utf-8'))
                                        w_fs.add(trn)
                                    t_any = True
                                else:
                                    self.log_colored(f"⚡ Перевод {m_nm} [Интерфейс] - {len(kt)} строк", "cyan")
                                    for k, v in self.translate_engine(kt, eng, l_set, ctx=m_nm).items():
                                        fd[k] = v
                                    od = json.dumps(fd, ensure_ascii=False, indent=2).encode('utf-8')
                                    if o_mod == "resourcepack" and ah and trn not in w_fs:
                                        ah.writestr(trn, od)
                                        w_fs.add(trn)
                                    elif zout:
                                        zout.writestr(trn, od)
                                        ru_w.add(trn)
                                    t_any = True

                        elif self.var_books.get() and is_jb:
                            trn = re.sub(r'/en_us/', f"/{l_set['file']}/", i.filename, flags=re.IGNORECASE)
                            trt = trn.lower()
                            ah = dp_h if fl.startswith('data/') else rp_h
                            
                            try:
                                ed = load_lenient_json(zin.read(i))
                            except:
                                continue
                                
                            td = load_lenient_json(zin.read(t_fs[trt])) if trt in t_fs else {}
                            es = [s for s in extract_book_strings(ed) if s.strip()]
                            ts = [s for s in extract_book_strings(td) if s.strip()] if td else []
                            kt = {}
                            fs = []
                            
                            for idx, s in enumerate(es):
                                if is_technical_term(s):
                                    fs.append(s)
                                    continue
                                if m_ovr == "append" and idx < len(ts) and ts[idx].strip():
                                    fs.append(ts[idx])
                                    if ts[idx] == s and re.search(r'[a-zA-Z]', s):
                                        kt[str(idx)] = s
                                else:
                                    fs.append(s)
                                    if re.search(r'[a-zA-Z]', s):
                                        kt[str(idx)] = s
                                        
                            te = len([s for s in es if re.search(r'[a-zA-Z]', s) and not is_technical_term(s)])
                            
                            if te > 0:
                                if m_ovr == "skip" and (te - len(kt)) >= te * 0.9:
                                    if o_mod == "resourcepack" and trt in t_fs and ah and trn not in w_fs:
                                        ah.writestr(trn, zin.read(t_fs[trt]))
                                        w_fs.add(trn)
                                elif len(kt) == 0 and m_ovr == "append":
                                    if o_mod == "resourcepack" and ah and trn not in w_fs:
                                        inject_book_strings(ed, iter(fs))
                                        od = json.dumps(ed, ensure_ascii=False, indent=2).encode('utf-8')
                                        ah.writestr(trn, od)
                                        w_fs.add(trn)
                                        if trn != i.filename and i.filename not in w_fs:
                                            try:
                                                ah.writestr(i.filename, od)
                                                w_fs.add(i.filename)
                                            except:
                                                pass
                                    t_any = True
                                else:
                                    self.log_colored(f"⚡ Перевод {m_nm} [Книга JSON / Датапак] - {len(kt)} строк", "magenta")
                                    td_rt = self.translate_engine(kt, eng, l_set, ctx=m_nm)
                                    for idx in range(len(fs)):
                                        if str(idx) in td_rt:
                                            fs[idx] = td_rt[str(idx)]
                                            
                                    inject_book_strings(ed, iter(fs))
                                    od = json.dumps(ed, ensure_ascii=False, indent=2).encode('utf-8')
                                    
                                    if o_mod == "resourcepack" and ah and trn not in w_fs:
                                        ah.writestr(trn, od)
                                        w_fs.add(trn)
                                        if trn != i.filename and i.filename not in w_fs:
                                            try:
                                                ah.writestr(i.filename, od)
                                                w_fs.add(i.filename)
                                            except:
                                                pass
                                    elif zout:
                                        zout.writestr(trn, od)
                                        ru_w.add(trn)
                                    t_any = True

                        elif self.var_books.get() and is_mb:
                            if '/en_us/' in fl:
                                trn = re.sub(r'/en_us/', f"/{l_set['file']}/", i.filename, flags=re.IGNORECASE)
                            else:
                                trn = i.filename
                                
                            trt = trn.lower()
                            l_reg = l_set.get('regex', r'[А-Яа-яЁё]')
                            ah = dp_h if fl.startswith('data/') else rp_h
                            
                            try:
                                et = zin.read(i).decode('utf-8-sig', errors='ignore')
                            except:
                                continue
                                
                            tt = zin.read(t_fs[trt]).decode('utf-8-sig', errors='ignore') if trt in t_fs else ""
                            
                            el = et.split('\n')
                            tl = tt.split('\n') if tt else []
                            
                            kt = {}
                            mp = {}
                            fln = []
                            in_y = False
                            
                            for idx, s in enumerate(el):
                                ss = s.strip()
                                if ss == '---':
                                    in_y = not in_y
                                    fln.append(s)
                                    continue
                                    
                                if in_y:
                                    if ss.lower().startswith('title:'):
                                        m = re.match(r'^(\s*title\s*:\s*[\'"]?)(.*?)([\'"]?)$', s, re.IGNORECASE)
                                        if m and re.search(r'[a-zA-Z]', m.group(2)):
                                            p, t, sf = m.groups()
                                            mp[str(idx)] = (p, sf)
                                            if m_ovr == "append" and idx < len(tl) and re.search(l_reg, tl[idx]):
                                                fln.append(tl[idx])
                                            else:
                                                fln.append(s)
                                                kt[str(idx)] = t
                                        else:
                                            fln.append(s)
                                    else:
                                        fln.append(s)
                                    continue
                                    
                                if ss.startswith('<') or ss.startswith('!['):
                                    fln.append(s)
                                    continue
                                    
                                if not ss or not re.search(r'[a-zA-Z]', s) or is_technical_term(s):
                                    fln.append(s)
                                    continue
                                    
                                if m_ovr == "append" and idx < len(tl) and tl[idx].strip() and re.search(l_reg, tl[idx]):
                                    fln.append(tl[idx])
                                else:
                                    fln.append(s)
                                    kt[str(idx)] = s

                            if len(kt) > 0:
                                self.log_colored(f"⚡ Перевод {m_nm} [Книга MD] - {len(kt)} строк", "magenta")
                                td_rt = self.translate_engine(kt, eng, l_set, ctx=m_nm)
                                
                                for idx_s, tv in td_rt.items():
                                    idx_i = int(idx_s)
                                    if idx_s in mp:
                                        p, s = mp[idx_s]
                                        fln[idx_i] = p + tv + s
                                    else:
                                        fln[idx_i] = tv
                                        
                                od = '\n'.join(fln).encode('utf-8')
                                
                                if o_mod == "resourcepack" and ah and trn not in w_fs:
                                    ah.writestr(trn, od)
                                    w_fs.add(trn)
                                    if trn != i.filename and i.filename not in w_fs:
                                        try:
                                            ah.writestr(i.filename, od)
                                            w_fs.add(i.filename)
                                        except:
                                            pass
                                elif zout:
                                    zout.writestr(trn, od)
                                    ru_w.add(trn)
                                t_any = True
                            else:
                                if o_mod == "resourcepack" and ah and trn not in w_fs:
                                    ah.writestr(trn, '\n'.join(fln).encode('utf-8'))
                                    w_fs.add(trn)
                                elif o_mod == "inplace" and zout:
                                    zout.writestr(trn, '\n'.join(fln).encode('utf-8'))
                                    ru_w.add(trn)

                    if o_mod == "inplace" and zout:
                        for i in zin.infolist():
                            if (tf in i.filename.lower() or f"/{l_set['file']}/" in i.filename.lower()) and i.filename not in ru_w:
                                try:
                                    zout.writestr(i, zin.read(i))
                                except:
                                    pass
                finally:
                    if zout:
                        zout.close()
                        
            if o_mod == "inplace":
                if t_any and self.is_running:
                    shutil.move(tmp, fp)
                else:
                    os.remove(tmp)
            else:
                if os.path.exists(tmp):
                    os.remove(tmp)
                    
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            self.log_colored(f"❌ Ошибка в {m_nm}: {e}", "red")

    def process_snbt(self, fp, eng, m_ovr, l_set):
        if not self.var_quests.get():
            return
            
        fn = os.path.basename(fp)
        l_reg = l_set.get('regex', r'[А-Яа-яЁё]')
        bp = fp + ".bak"
        
        if not os.path.exists(bp):
            shutil.copy2(fp, bp)
            
        cp = fp if m_ovr == "append" else bp
        
        try:
            with open(cp, 'r', encoding='utf-8') as f:
                c = f.read()
                
            stt = []
            # 1. Извлекаем одиночные строки
            for m in re.finditer(r'(?:"|)(?:title|subtitle|text)(?:"|)\s*:\s*"((?:[^"\\]|\\.)*)"', c, re.IGNORECASE):
                v = m.group(1)
                if v.strip() and not is_translation_key(v) and re.search(r'[a-zA-Z]', v): 
                    if m_ovr == "append" and re.search(l_reg, v):
                        continue
                    stt.append(v)
                    
            # 2. Безопасно извлекаем строки из массивов (обходим баг с внутренними скобками)
            for m in re.finditer(r'(?:"|)(?:description|text)(?:"|)\s*:\s*\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\]', c, re.IGNORECASE):
                for sm in re.finditer(r'"((?:[^"\\]|\\.)*)"', m.group(0)):
                    v = sm.group(1)
                    if v.strip() and not is_translation_key(v) and re.search(r'[a-zA-Z]', v): 
                        if m_ovr == "append" and re.search(l_reg, v):
                            continue
                        stt.append(v)
                        
            stt = list(set(stt))
            if len(stt) == 0:
                return
                
            if m_ovr == "skip":
                with open(fp, 'r', encoding='utf-8') as f:
                    if re.search(l_reg, f.read()):
                        return

            self.log_colored(f"⚡ Перевод {fn} [Квесты] - {len(stt)} строк", "yellow")
            
            chunk_dict = {str(i): v for i, v in enumerate(stt)}
            td = self.translate_engine(chunk_dict, eng, l_set, ctx=fn)
            tm = {stt[i]: td.get(str(i), stt[i]) for i in range(len(stt))}
            
            # 3. Подставляем переводы одиночных строк
            def rs(m):
                nv = tm.get(m.group(2), m.group(2)).replace('\\"', '"').replace('"', '\\"')
                return f'{m.group(1)}: "{nv}"'
                
            c = re.sub(r'(?:"|)(title|subtitle|text)(?:"|)\s*:\s*"((?:[^"\\]|\\.)*)"', rs, c, flags=re.IGNORECASE)
            
            # 4. Аккуратно заменяем переводы внутри блоков массивов
            def ra(m):
                key = m.group(1)
                array_block = m.group(2)
                def ri(sm):
                    nv = tm.get(sm.group(1), sm.group(1)).replace('\\"', '"').replace('"', '\\"')
                    return f'"{nv}"'
                replaced_array = re.sub(r'"((?:[^"\\]|\\.)*)"', ri, array_block)
                return f'{key}: {replaced_array}'
                
            c = re.sub(r'(?:"|)(description|text)(?:"|)\s*:\s*(\[\s*(?:"(?:[^"\\]|\\.)*"\s*,?\s*)*\])', ra, c, flags=re.IGNORECASE)
            
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(c)
                
        except Exception as e:
            self.log_colored(f"❌ Ошибка квеста {fn}: {e}", "red")

if __name__ == '__main__':
    app = TranslatorApp()
    app.mainloop()
