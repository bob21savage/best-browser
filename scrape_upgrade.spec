# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['scrape_upgrade.py'],
    pathex=[],
    binaries=[],
    datas=[
        (r'C:\Users\bpier\Desktop\scrape\scrape\cinema.ico', '.'),
        ('templates', 'templates'), 
        ('static', 'static')
    ],
    hiddenimports=[
        'quart',
        'aiohttp',
        'asyncio',
        'bs4',
        'requests',
        'requests_html',
        'lxml',
        'urllib3',
        'chardet',
        'certifi',
        'idna',
        'python_anticaptcha',
        'robotexclusionrulesparser',
        'python_dotenv',
        'dotenv',
        'brotli',
        'hypercorn',
        'hypercorn.asyncio',
        'wsproto',
        'h11',
        'priority',
        'toml',
        'typing_extensions',
        'html5lib',
        'flask',
        'flask_socketio'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='scraper_upgrade',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=r'C:\Users\bpier\Desktop\scrape\scrape\cinema.ico',
)
