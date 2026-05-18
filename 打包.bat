@echo off
cd /d "%~dp0"
taskkill /f /im VintedTool.exe >nul 2>&1
timeout /t 1 /nobreak >nul
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
python -m PyInstaller vinted_build.spec
echo Done!
pause
