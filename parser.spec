# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['interface.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('assets', 'assets'),
        ('drivers', 'drivers')  # папка с драйверами
    ],
    hiddenimports=[
        'selenium',
        'webdriver_manager',
        'tkinter',
        'win32api',
        'win32con',
        'win32gui'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MyApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Сжатие
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Не показывать консоль
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

)

# Для сборки в один файл
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MyApp'
)