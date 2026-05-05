@echo off
chcp 65001 > nul

echo [Build Starting...]
cd /d "%~dp0.."

echo [Cleaning up previous builds...]
if exist _build rmdir /s /q _build
if exist _dist rmdir /s /q _dist

echo [Running PyInstaller...]
:: --workpath와 --distpath를 명시하여 기존 build 폴더와 충돌을 방지합니다.
pyinstaller --noconfirm --workpath "_build" --distpath "_dist" "build\bithumbSplit.spec"

echo [Build Finished!]
echo 결과물은 _dist 폴더에 생성되었습니다.
pause
