# bithumbSplit.spec
# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

# spec 파일이 build/ 폴더 안에 있으므로 루트 경로는 한 단계 위임
PROJ_ROOT = os.path.abspath(os.path.join(os.getcwd()))

a = Analysis(
    ['../gui/gui_app.py'],
    pathex=[PROJ_ROOT],
    binaries=[],
    datas=[
        ('../.env', '.'),
        ('../config/settings.py', 'config'),
        ('../api/api.py', 'api'),
        ('../utils/telegram.py', 'utils'),
        ('../utils/logger.py', 'utils'),
        ('../utils/file_io.py', 'utils'),
        ('../utils/log_config.py', 'utils'),
        ('../utils/telegram_bot.py', 'utils'),
        ('../utils/dashboard.py', 'utils'),
        ('../utils/watchdog.py', 'utils'),
        ('../strategy/auto_trade.py', 'strategy'),
        ('../shared/state.py', 'shared'),
    ],
    hiddenimports=[
        'strategy.auto_trade',
        'api.api',
        'config.settings',
        'utils.telegram',
        'utils.logger',
        'utils.file_io',
        'utils.log_config',
        'utils.telegram_bot',
        'utils.dashboard',
        'utils.watchdog',
        'shared.state',
        'flask',
        'pystray',
        'PIL',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='bithumbSplit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="../images/bithumbSplit.png"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bithumbSplit'
)

