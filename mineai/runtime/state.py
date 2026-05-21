import threading
import time
from dataclasses import dataclass, field


@dataclass
class JobState:
    is_running: bool = False
    is_paused: bool = False
    total_strings: int = 0
    translated_strings: int = 0
    start_time: float | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def wait_if_paused(self) -> None:
        while self.is_paused and self.is_running:
            time.sleep(0.5)

    def should_run(self) -> bool:
        with self._lock:
            return self.is_running

    def stop(self) -> None:
        with self._lock:
            self.is_running = False
            self.is_paused = False

    def increment_translated(self, count: int = 1) -> None:
        with self._lock:
            self.translated_strings += count

    def eta_text(self) -> str:
        if not self.start_time or self.translated_strings == 0:
            return "расчёт..."
        elapsed = time.time() - self.start_time
        if elapsed < 5:
            return "расчёт..."
        remaining = self.total_strings - self.translated_strings
        if remaining <= 0:
            return "готово"
        rate = self.translated_strings / elapsed
        seconds = remaining / rate
        if seconds < 60:
            return f"≈ {int(seconds)} сек"
        if seconds < 3600:
            return f"≈ {int(seconds // 60)} мин {int(seconds % 60)} сек"
        return f"≈ {int(seconds // 3600)} ч {int((seconds % 3600) // 60)} мин"
