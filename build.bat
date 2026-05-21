@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =========================================
echo  MineAI Translator — сборка EXE
echo =========================================
echo.

echo [1/3] Установка и обновление зависимостей...
python -m pip install -r requirements.txt pyinstaller -q
if errorlevel 1 (
    echo Ошибка: не удалось установить пакеты. Проверьте Python 3.10+
    pause
    exit /b 1
)

echo [2/3] Запуск сборки через PyInstaller...
python -m PyInstaller --noconfirm --clean --noconsole --onefile --name=MineAI_Translator mineai/__main__.py
if errorlevel 1 (
    echo Ошибка сборки.
    pause
    exit /b 1
)

echo.
echo [3/3] Готово!
echo    EXE-файл успешно создан: dist\MineAI_Translator.exe
echo.
echo Рядом с EXE положите при необходимости:
echo    settings.ini, dictionary.json, cache.json
echo.
pause