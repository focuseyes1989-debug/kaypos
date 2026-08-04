"""Build Cashier Mode.exe from the existing ZAY POS source tree."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

APP_NAME = "Cashier Mode"
SPEC_NAME = "Cashier_Mode.spec"


def clean_previous_build():
    for path in (Path("build") / "Cashier_Mode", Path("dist") / APP_NAME, Path("dist") / f"{APP_NAME}.exe"):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def write_spec():
    icon = "assets/icons/app_icon.ico"
    icon_expr = repr(icon) if os.path.exists(icon) else "None"

    spec = f'''# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_submodules

sqlite_binaries = []
python_dll_dir = os.path.join(sys.base_prefix, 'DLLs')
for sqlite_name in ('_sqlite3.pyd', 'sqlite3.dll'):
    sqlite_path = os.path.join(python_dll_dir, sqlite_name)
    if os.path.exists(sqlite_path):
        sqlite_binaries.append((sqlite_path, '.'))

hiddenimports = [
    'PyQt6.QtSvg',
    'PyQt6.QtSvgWidgets',
    'PyQt6.QtPrintSupport',
    'PyQt6.QtSql',
    'loguru',
    'sqlite3',
    '_sqlite3',
]

# Checkout/payment modules contain a few dynamic imports.
hiddenimports += collect_submodules('ui.sales_page.checkout_handler')

a = Analysis(
    ['cashier_main.py'],
    pathex=[],
    binaries=sqlite_binaries,
    datas=[
        ('assets', 'assets'),
        ('version.txt', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'tcl', 'tk',
        'pandas', 'scipy', 'IPython', 'jupyter', 'notebook',
        'matplotlib', 'matplotlib.pyplot', 'matplotlib.backends',
        'sounddevice', 'speech_recognition',
        'selenium', 'playwright',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name={APP_NAME!r},
    debug=False,
    bootloader_ignore_signals=False,
    exclude_binaries=True,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon={icon_expr},
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name={APP_NAME!r},
)
'''
    Path(SPEC_NAME).write_text(spec, encoding="utf-8")


def main():
    os.chdir(Path(__file__).resolve().parent)
    clean_previous_build()
    write_spec()
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", SPEC_NAME]
    print("Building Cashier Mode.exe...")
    subprocess.run(command, check=True)
    print(f"Done: {Path('dist') / APP_NAME / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()
