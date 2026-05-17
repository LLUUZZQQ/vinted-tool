# -*- coding: utf-8 -*-
"""
Vinted 抓图工具 — PyInstaller 打包脚本
用法：pyinstaller vinted_build.spec
输出：dist/VintedTool.exe
"""
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

selenium_hidden = collect_submodules('selenium')

a = Analysis(
    ['vinted_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('vinted_style.qss', '.'),
        ('chromedriver.exe', '.'),
    ],
    hiddenimports=[
        'license_system',
        'update_checker',
        'Vinted_抓图',
        'cryptography',
        'piexif', 'numpy',
        'PIL', 'PIL.Image', 'PIL.ImageEnhance', 'PIL.ImageFilter',
        'PIL.ImageDraw', 'PIL.ImageFont',
        'win32api', 'win32con', 'win32com', 'win32com.client',
        'requests', 'urllib3',
        'configparser', 'shutil', 'hashlib', 'string', 'threading',
    ] + selenium_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'pandas', 'jedi', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='VintedTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
