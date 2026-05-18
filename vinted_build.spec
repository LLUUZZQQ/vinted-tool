# -*- coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['vinted_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('vinted_style.qss', '.'),
        ('chromedriver.exe', '.'),
    ],
    hiddenimports=[
        'license_system', 'update_checker', 'Vinted_抓图',
        'cryptography',
        'piexif', 'numpy',
        'PIL', 'PIL.Image', 'PIL.ImageEnhance', 'PIL.ImageFilter',
        'PIL.ImageDraw', 'PIL.ImageFont',
        'selenium', 'selenium.webdriver',
        'selenium.webdriver.chrome', 'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service', 'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.common', 'selenium.webdriver.common.by',
        'selenium.webdriver.support', 'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.common', 'selenium.common.exceptions',
        'win32api', 'win32con', 'win32com', 'win32com.client',
        'requests', 'urllib3',
        'configparser', 'shutil', 'hashlib', 'string', 'threading',
    ],
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
