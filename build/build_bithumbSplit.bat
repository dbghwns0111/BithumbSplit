@echo off
chcp 65001 > nul

echo [Build Starting...]
cd /d "%~dp0.."

echo [Cleaning up previous builds...]
if exist build\bithumbSplit rmdir /s /q build\bithumbSplit
if exist dist rmdir /s /q dist

echo [Running PyInstaller...]
pyinstaller build\bithumbSplit.spec --noconfirm

echo [Build Finished!]
pause
