# 🌍 MineAI Translator (The Ultimate Modpack Localizer)

*Read this in other languages: [Русский](#-mineai-translator-ультимативный-локализатор-сборок)*

**MineAI Translator** is a powerful, smart, and safe tool for automatically translating Minecraft modpacks (mods, quests, and guidebooks) into **11 different languages**.

This program was created to solve the main problem of translating large modpacks: standard translators break the code hidden inside the text (variables like `%s`, markdown links, item tags), causing the game to crash or hide interfaces (as is common with *Applied Energistics 2* or *Patchouli* guidebooks). Our tool uses a **"Titanium Shield"** system that masks the system code before sending it to the translator and safely puts it back in place.

## 🌍 Multi-Language Support
You can translate your modpack from English into any of the following languages:
**Russian, Spanish, German, French, Simplified Chinese, Japanese, Portuguese, Italian, Polish, Korean, and English (UK).**

## 🖥️ User-Friendly Interface
The program features a modern Graphical User Interface (GUI). You don't need to write console commands — simply select your modpack folder, check the desired boxes, choose your target language, and click "Start".

![Main Window](https://github.com/Thedrezik/MineAI-Modpack-Translator/blob/main/interface.png?raw=true)

---

## 📥 Installation & Usage (Download .exe)

You don't need to install Python or mess with code! You can download the ready-to-use application.

1. Go to the [Releases](https://github.com/Thedrezik/MineAI-Modpack-Translator/releases) tab on the right.
2. Download the latest **`MineAI_Translator.exe`** file.
3. Place it in a convenient folder and run it with a double click.

*(For advanced users and developers, instructions on running from source code are at the bottom of the page).*

---

## ✨ Key Features (Why is this the best translator?)

* 🛡️ **Format Protection (Titanium Shield):** Smart regular expressions protect macros `$(#AE)`, tags `<item:minecraft:dirt>`, Markdown links `](url)`, and YAML headers (`---`) from being corrupted by the translator.
* 🛠️ **Auto-Fix Cache:** Machine translators often make mistakes (e.g., adding spaces in variables: `% s` instead of `%s`). On every run, the program scans its cache and **automatically fixes** broken brackets, links, and variables, ensuring perfect formatting.
* 📖 **Custom Dictionary (`dictionary.json`):** The program automatically generates a dictionary file. If the translator stubbornly translates "Raw Copper" incorrectly, just add a rule to the dictionary, and the script will automatically replace it throughout the entire modpack!
* 🧠 **Local AI Support:** Integration with KoboldCPP for translating text while preserving game lore and context.
* ☁️ **Cloud AI via OpenRouter:** Connect elite neural networks (like Qwen, Claude, or GPT) in one click without using your video card.
* 🔌 **Any OpenAI-compatible Provider:** Plug in literally any chat-completions endpoint — `localhost:8080`, OpenCode Zen, Ollama (`/v1`), LM Studio, llama.cpp server, vLLM, Together, Groq — by entering Base URL, API key, model and (optional) extra headers.
* 📖 **Glossary-aware AI:** The AI reads `glossary.md` (markdown tables) and is forced to use the canonical translations. Optionally it can suggest new terms, which are auto-appended to a managed `## Авто-добавлено ИИ` section between markers, so the human-curated part of the file stays untouched.
* ⚡ **High Speed:** When using Google Translate, the program sends requests in batches using multi-threading, translating thousands of lines in minutes.
* 📦 **Safe Packaging:** The program generates a ready-to-use `Resource Pack` or `Data Pack` without damaging your original `.jar` mod files.

---

## 🎛️ Processing Modes

The program offers three processing modes to adapt to any situation:

1. **Append (Keep old translations)**
   * *How it works:* Finds only **new, untranslated lines** and translates them, leaving your existing translations untouched.
   * *Why use it:* Perfect for updating a modpack! If a mod updates with 50 new items, it translates only those in seconds.
2. **Skip (If 90%+ done)**
   * *How it works:* If a mod is already 90% or more translated, the program skips it entirely.
   * *Why use it:* Saves time on massive modpacks where authors might have left a few technical lines untranslated.
3. **Force (Translate from scratch)**
   * *How it works:* Completely ignores existing translations and re-translates all text from scratch.
   * *Why use it:* If the current translation is terrible (machine-translated) and you want to rewrite it using a high-quality AI.

---

## ⚙️ Strategy: How to Get the Perfect Result

For the best quality, a **combined approach (Creating two resource packs)** is recommended.

### Step 1. Interface Translation (Fast & Technical)
Mod interfaces (item names, simple descriptions) don't require literary talent.
1. Select **only "Interface (Mods)"**.
2. Engine: **Google** | Mode: **Append**.
3. Name the resource pack: `Mods_UI_Translated`.
*Result: In 2-3 minutes, you will translate 90% of the modpack (tens of thousands of lines).*

### Step 2. Quests and Guidebooks (Lore & High Quality)
Books and quests contain stories and jokes. Google will translate them poorly. This is where AI shines!
1. Select **"Guidebooks" and "Quests"** (uncheck Interface).
2. Engine: **AI Provider** (Local AI or OpenRouter) | Mode: **Force** (to overwrite bad old translations).
3. Name the resource pack: `Quests_Lore_Translated`.
*Result: The text will read like a well-written book.*

> 💡 **How to use in-game:** Place both archives in your `resourcepacks` folder. Enable both, but **put `Quests_Lore_Translated` ABOVE `Mods_UI_Translated`**.

---

## 🗃️ Isolated Caching System

To avoid translating the same lines twice, the program uses a **dual independent cache**, as the styles of different engines vary:
* `cache.json` — Machine translation cache (Google/DeepL).
* `ai_cache.json` — High-quality AI translation cache (KoboldCPP/OpenRouter).
*If the program closes unexpectedly, you won't lose a single translated line.*

---

## 🤖 AI Configuration (Artificial Intelligence)

### Option 1: Cloud AI (OpenRouter) — Recommended for weak PCs
1. Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys).
2. In **Settings → OpenRouter**, enter your key and the desired model ID (e.g., `google/gemma-2-9b-it:free` or `qwen/qwen-2.5-72b-instruct`).
3. In the main window, choose the **AI Engine** and select **OpenRouter (cloud)**.

### Option 2: Local AI (KoboldCPP)
The program launches the `koboldcpp.exe` engine itself (just place it in the `AI` folder). You only need to download a language model in **`.gguf`** format.

### Option 3: Custom OpenAI-compatible Provider
For literally anything else with a `/v1/chat/completions` endpoint:
1. Open **Settings → Custom AI**.
2. Fill in:
   * **Имя провайдера** — any label (shown in the log).
   * **Base URL** — e.g. `http://localhost:8080/v1`, `https://api.opencode.zen/v1`, `http://127.0.0.1:11434/v1` for Ollama, etc. The path `/chat/completions` is appended automatically.
   * **API key** — leave blank for local servers that don't require auth.
   * **ID модели** — e.g. `qwen2.5:14b`, `local-model`, whatever your endpoint expects.
   * **Auth scheme** — `bearer` (default), `x-api-key`, `api-key` or `none`.
   * **Доп. заголовки** — optional JSON, e.g. `{"X-Provider": "opencode"}`.
3. In the main window choose **AI Engine → Custom (OpenAI-compatible)**.

### Glossary (`glossary.md`)
When AI translation is on and the glossary is enabled (Settings → Глоссарий), MineAI:
* Loads all markdown tables of the form `| Original | Перевод | Примечание |` from `glossary.md`.
* Per batch, finds terms that appear in the source strings and injects them into the prompt as **mandatory** translations.
* If "Разрешить ИИ дописывать новые термины" is on, the model may return a `__glossary_additions__` JSON object, and those new pairs are written into the managed **`## Авто-добавлено ИИ`** section (between `<!-- AUTO_GLOSSARY_START -->` and `<!-- AUTO_GLOSSARY_END -->` markers) at the end of the file. Your hand-written sections are never touched.

#### GPU Offloading
* **0 (CPU Only):** Runs on your processor (Slow).
* **10-50:** Balanced (Partially in VRAM, partially in RAM).
* **99 (Max):** Entire model loaded into Video RAM. Maximum speed.

#### Recommended Models (Format: Q4_K_M or Q5_K_M)
1. **Lightweight (7B - 8B)** *(Requires: ~6-8 GB VRAM)*:
   * Qwen 2.5 (7B): [Download from Hugging Face](https://huggingface.co/paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF/tree/main)
   * Llama 3.1 (8B): [Download from Hugging Face](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)
2. **Medium (14B)** *(Requires: ~10-12 GB VRAM)*:
   * Qwen 2.5 (14B): [Download from Hugging Face](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF)
3. **Heavyweights (32B+)** *(Requires: 16+ GB VRAM)*:
   * Qwen 2.5 (32B): [Download from Hugging Face](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF)

---

## 🛠️ Running from Source & Architecture

### Project Structure
mineai/
  config.py           # settings.ini manager
  constants.py        # Languages, pack_formats, ignore lists
  text_processing.py  # Titanium shield masks, polish, smart glue
  json_utils.py       # Lenient JSON parser, book paths
  cache.py            # Thread-safe translation cache
  engines/            # Google, DeepL, Kobold, OpenRouter API
  processors/         # JAR parsing, SNBT formatting, analysis
  output/             # Zip resourcepack/datapack building
  runtime/            # Translation jobs, AI launcher background thread
  gui/                # CustomTkinter modern UI

### How to Run:
1. Install Python 3.10+.
2. Run in terminal: `pip install -r requirements.txt`.
3. Launch the module: `python -m mineai`.

### How to Compile into .exe:
If you modified the code and want to build your own executable without a console window, simply run the provided batch file:
`build.bat`

The compiled standalone app will appear in the `dist/` folder as `MineAI_Translator.exe`.

---
---

# 🇷🇺 MineAI Translator (Ультимативный Локализатор Сборок)

**MineAI Translator** — это мощный, умный и безопасный инструмент для автоматического перевода сборок Minecraft (модов, квестов и справочников) на **11 различных языков**.

Программа создана для решения главной проблемы перевода больших сборок: обычные переводчики ломают программный код внутри текста (переменные `%s`, ссылки, теги предметов), из-за чего игра выдает ошибки или скрывает интерфейс (как это часто бывает со справочниками *Applied Energistics 2* или *Patchouli*). Наш инструмент использует систему **«Титанового щита»**, которая маскирует системный код перед отправкой переводчику и безопасно возвращает его на место.

## ✨ Главные особенности (Почему этот переводчик лучший?)

* 🛡️ **Защита форматирования (Титановый Щит):** Умные регулярные выражения защищают макросы `$(#AE)`, теги `<item:minecraft:dirt>`, ссылки Markdown `](url)` и шапки YAML (`---`) от искажений.
* 🛠️ **Самолечение кэша (Auto-Fix):** Машинные переводчики часто ошибаются (ставят пробелы в переменных: `% s` вместо `%s`). При каждом запуске программа сканирует свой кэш и **автоматически чинит** сломанные скобки, ссылки и переменные.

* 📖 **Пользовательский словарь (`dictionary.json`):** Если переводчик упорно переводит "Raw Copper" как "Сыромятная медь", просто добавьте правило в созданный словарь, и скрипт заменит всё на "Сырая медь" во всей сборке!
* 🧠 **Локальные Нейросети:** Интеграция с KoboldCPP для перевода текста с полным сохранением игрового лора и контекста.
* ☁️ **Облачный ИИ через OpenRouter:** Подключайте топовые нейросети (Qwen, Claude, GPT) в один клик без нагрузки на собственную видеокарту!
* ⚡ **Высокая скорость:** Многопоточный Google Translate отправляет запросы пачками, переводя тысячи строк за считанные минуты.
* 📦 **Безопасная упаковка:** Программа генерирует готовый Resource Pack или Data Pack, вообще не повреждая ваши оригинальные `.jar` файлы модов.

## 🤖 Настройка Искусственного Интеллекта (AI)

### Вариант 1: Облачный ИИ (OpenRouter) — Идеально для слабых ПК
1. Получите API-ключ на сайте [openrouter.ai/keys](https://openrouter.ai/keys).
2. В **Настройки → OpenRouter** укажите ваш ключ и ID модели (например, `google/gemma-2-9b-it:free` или `qwen/qwen-2.5-72b-instruct`).
3. В главном окне выберите движок **Нейросеть (ИИ) → OpenRouter (облако)**.

### Вариант 2: Локальный ИИ (KoboldCPP)
Программа сама запускает движок `koboldcpp.exe` (просто положите его в папку `AI`). Вам нужно лишь скачать языковую модель формата **`.gguf`**.

### Вариант 3: Custom (OpenAI-совместимый провайдер)
Для любых других сервисов и серверов: localhost (`llama.cpp server`, `LM Studio`, `Ollama /v1`, `vLLM`), OpenCode Zen, Together, Groq и т.д.
1. Откройте **Настройки → Custom AI**.
2. Заполните: имя провайдера (для лога), **Base URL** (до `/chat/completions`, обычно оканчивается на `/v1`), API-ключ (если нужен), ID модели, схему авторизации (`bearer`/`x-api-key`/`api-key`/`none`) и при необходимости доп. заголовки в JSON.
3. В главном окне выберите **Нейросеть (ИИ) → Custom (OpenAI-совместимый)**.

### Глоссарий (`glossary.md`)
В режиме ИИ программа подгружает таблицы вида `| Оригинал | Перевод | Примечание |` из `glossary.md` и принудительно подставляет нужные термины в промпт. Если включить «Разрешить ИИ дописывать новые термины», модель сможет предложить новые пары, и они допишутся в управляемую секцию `## Авто-добавлено ИИ` между маркерами `<!-- AUTO_GLOSSARY_START -->` / `<!-- AUTO_GLOSSARY_END -->`. Ручной контент глоссария при этом не трогается.

* **Нагрузка на GPU (0):** Только процессор (Медленно).
* **Нагрузка на GPU (99):** Модель полностью в видеопамяти (VRAM). Максимальная скорость.

#### Рекомендуемые модели для скачивания:
1. **Легкие (7B - 8B)** (~6-8 ГБ VRAM):
   * Qwen 2.5 (7B): [Скачать с Hugging Face](https://huggingface.co/paultimothymooney/Qwen2.5-7B-Instruct-Q4_K_M-GGUF/tree/main)
   * Llama 3.1 (8B): [Скачать с Hugging Face](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF)
2. **Средние (14B)** (~10-12 ГБ VRAM):
   * Qwen 2.5 (14B): [Скачать с Hugging Face](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct-GGUF)
3. **Тяжелые (32B+)** (От 16 ГБ VRAM):
   * Qwen 2.5 (32B): [Скачать с Hugging Face](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF)

---

## 🛠️ Запуск из исходного кода & Компиляция

1. Установите Python 3.10+.
2. Установите зависимости: `pip install -r requirements.txt`.
3. Запуск приложения: `python -m mineai`.

Для сборки собственного `.exe` файла без окна консоли используйте готовый батник:
`build.bat`
(Результат появится в папке `dist/MineAI_Translator.exe`).

## License
MIT
