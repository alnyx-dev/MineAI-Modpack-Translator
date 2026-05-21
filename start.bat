@echo off
chcp 65001 >nul
echo Installing dependencies...
python -m pip install -r requirements.txt -q
echo =========================================
echo Starting MineAI Translator...
python -m mineai
pause
