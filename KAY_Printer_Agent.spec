# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('PyQt6.QtPrintSupport')
hiddenimports += ['PyQt6.QtPdf', 'requests', 'urllib3', 'printer_agent_gui', 'printer_picture_page', 'printer_picture_print', 'utils.single_instance']

a = Analysis(
    ['printer_agent.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/icons', 'assets/icons')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KAY_Printer_Agent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app_icon.ico',
)
