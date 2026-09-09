# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['local_print_bridge.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt uses the Windows ICU API. Never bundle an unrelated ICU found on PATH
# (for example Poppler's ICU), which exports a different API and breaks QtCore.
a.binaries = [entry for entry in a.binaries if entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower() != 'icuuc.dll']
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='KAY_Touch_Print_Bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
