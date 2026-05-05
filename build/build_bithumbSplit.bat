@echo off
chcp 65001 > nul

echo [Build Starting...]
cd /d "%~dp0.."

echo [Cleaning up previous builds...]
if exist _build rmdir /s /q _build
if exist _dist rmdir /s /q _dist

echo [Running PyInstaller...]
:: Use --workpath and --distpath to avoid conflicts with existing folders
pyinstaller --noconfirm --workpath "_build" --distpath "_dist" "build\bithumbSplit.spec"

echo [Build Finished!]
echo Results are in the _dist folder.
pause
