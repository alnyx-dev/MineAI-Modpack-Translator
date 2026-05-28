"""
Глоссарий локализации: чтение/запись markdown-таблиц + lookup релевантных терминов.

Формат файла (`glossary.md`):
* Произвольный markdown-текст (правила, журнал, заметки) сохраняется как есть.
* Из всех таблиц вида ``| Оригинал | Перевод | Примечание |`` (или 2 колонки)
  извлекаются пары EN→RU.
* Новые термины, предложенные ИИ, дописываются в управляемую секцию
  между маркерами ``<!-- AUTO_GLOSSARY_START -->`` и ``<!-- AUTO_GLOSSARY_END -->``.
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

AUTO_START = "<!-- AUTO_GLOSSARY_START -->"
AUTO_END = "<!-- AUTO_GLOSSARY_END -->"
AUTO_HEADER = "## Авто-добавлено ИИ"

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


@dataclass
class GlossaryEntry:
    src: str
    dst: str
    note: str = ""


@dataclass
class Glossary:
    """Загруженный глоссарий с возможностью lookup и дозаписи."""

    path: str
    entries: dict[str, GlossaryEntry] = field(default_factory=dict)
    _src_index: dict[str, str] = field(default_factory=dict)  # lowercase src -> original src
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    pending_additions: list[GlossaryEntry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def has(self, src: str) -> bool:
        return src.casefold() in self._src_index

    def get(self, src: str) -> GlossaryEntry | None:
        key = self._src_index.get(src.casefold())
        return self.entries.get(key) if key else None

    def relevant_for(self, texts: Iterable[str], *, limit: int = 60) -> dict[str, str]:
        """Возвращает {Оригинал: Перевод} для терминов, встречающихся в текстах."""
        if not self.entries:
            return {}
        haystack = " \n ".join(texts).casefold()
        if not haystack:
            return {}
        hits: dict[str, str] = {}
        # сортируем по длине ключа — длинные термины приоритетнее
        for key in sorted(self._src_index.keys(), key=len, reverse=True):
            if key in haystack:
                entry = self.entries[self._src_index[key]]
                hits[entry.src] = entry.dst
                if len(hits) >= limit:
                    break
        return hits

    def stage_additions(self, additions: dict[str, str] | Iterable[GlossaryEntry]) -> int:
        """Накопить предложения от ИИ. Возвращает число реально новых записей."""
        added = 0
        with self._lock:
            iterable: Iterable[GlossaryEntry]
            if isinstance(additions, dict):
                iterable = (GlossaryEntry(src=str(k), dst=str(v)) for k, v in additions.items())
            else:
                iterable = additions
            for entry in iterable:
                src = (entry.src or "").strip()
                dst = (entry.dst or "").strip()
                if not src or not dst:
                    continue
                if self.has(src):
                    continue
                # фильтр мусора: только настоящие термины (без табов/переносов)
                if "\n" in src or "\n" in dst:
                    continue
                if len(src) > 120 or len(dst) > 200:
                    continue
                key_cf = src.casefold()
                if any(p.src.casefold() == key_cf for p in self.pending_additions):
                    continue
                self.pending_additions.append(GlossaryEntry(src=src, dst=dst, note=entry.note))
                # также добавим в живой индекс, чтобы дубли в той же сессии не плодились
                self.entries[src] = self.pending_additions[-1]
                self._src_index[key_cf] = src
                added += 1
        return added

    def flush(self) -> int:
        """Дописать накопленные предложения в файл. Возвращает число записанных."""
        with self._lock:
            if not self.pending_additions:
                return 0
            if not self.path:
                self.pending_additions.clear()
                return 0
            try:
                text = _read_text(self.path)
            except FileNotFoundError:
                text = ""
            new_text, written = _append_auto_section(text, self.pending_additions)
            if written:
                _write_text(self.path, new_text)
            count = len(self.pending_additions)
            self.pending_additions.clear()
            return count


# ---------- загрузка / парсинг ----------------------------------------------

def load_glossary(path: str) -> Glossary:
    glossary = Glossary(path=path)
    if not path or not os.path.exists(path):
        return glossary
    try:
        text = _read_text(path)
    except OSError:
        return glossary
    for entry in _iter_table_entries(text):
        key_cf = entry.src.casefold()
        if key_cf in glossary._src_index:
            continue
        glossary.entries[entry.src] = entry
        glossary._src_index[key_cf] = entry.src
    return glossary


def _iter_table_entries(text: str) -> Iterable[GlossaryEntry]:
    in_code = False
    rows: list[list[str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if _TABLE_SEP.match(stripped):
            # предыдущая строка была заголовком таблицы
            if rows:
                header = rows[-1]
                rows = []
            continue
        m = _TABLE_ROW.match(line)
        if not m:
            # закончилась таблица
            if header is not None:
                yield from _emit_rows(header, rows)
            header = None
            rows = []
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if header is None:
            rows.append(cells)
        else:
            rows.append(cells)
    if header is not None and rows:
        yield from _emit_rows(header, rows)


def _emit_rows(header: list[str], rows: list[list[str]]) -> Iterable[GlossaryEntry]:
    # эвристика: первая колонка — оригинал, вторая — перевод, третья (если есть) — примечание
    # пропускаем таблицы, где заголовок явно не про термины (например "Файл | Заголовок")
    if len(header) < 2:
        return
    h0 = header[0].casefold()
    if h0 in {"файл", "file"}:
        return
    for row in rows:
        if len(row) < 2:
            continue
        src, dst = row[0], row[1]
        note = row[2] if len(row) > 2 else ""
        if not src or not dst:
            continue
        # пропускаем пары "X | X" (помечает «не переводится»)
        yield GlossaryEntry(src=src, dst=dst, note=note)


# ---------- запись ----------------------------------------------------------

def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _append_auto_section(text: str, additions: list[GlossaryEntry]) -> tuple[str, int]:
    """Вставить строки в управляемую секцию (или создать её)."""
    if not additions:
        return text, 0

    today = date.today().isoformat()
    new_rows = "\n".join(
        f"| {e.src} | {e.dst} | {e.note or f'Авто, {today}'} |" for e in additions
    )

    if AUTO_START in text and AUTO_END in text:
        start = text.index(AUTO_START) + len(AUTO_START)
        end = text.index(AUTO_END)
        body = text[start:end]
        # если внутри уже есть таблица — дописываем новые строки в конец таблицы
        if "|" in body:
            updated = body.rstrip() + "\n" + new_rows + "\n"
        else:
            updated = (
                "\n| Оригинал | Перевод | Примечание |\n|---|---|---|\n" + new_rows + "\n"
            )
        return text[:start] + "\n" + updated.lstrip("\n") + text[end:], len(additions)

    suffix = (
        f"\n\n{AUTO_HEADER}\n\n"
        f"{AUTO_START}\n"
        f"| Оригинал | Перевод | Примечание |\n"
        f"|---|---|---|\n"
        f"{new_rows}\n"
        f"{AUTO_END}\n"
    )
    if text and not text.endswith("\n"):
        text += "\n"
    return text + suffix, len(additions)


def ensure_auto_section(path: str) -> None:
    """Создаёт пустую AUTO-секцию, если её ещё нет. Используется при нормализации."""
    if not path or not os.path.exists(path):
        return
    text = _read_text(path)
    if AUTO_START in text:
        return
    suffix = (
        f"\n{AUTO_HEADER}\n\n"
        f"{AUTO_START}\n"
        f"| Оригинал | Перевод | Примечание |\n"
        f"|---|---|---|\n"
        f"{AUTO_END}\n"
    )
    if text and not text.endswith("\n"):
        text += "\n"
    _write_text(path, text + suffix)
