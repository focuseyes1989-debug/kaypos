"""Package the Cashier Mode executable for GitHub Release upload."""

import argparse
import os
import sys
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_DIR = PROJECT_ROOT / "update_build"


def find_cashier_exe() -> Path:
    candidates = [
        DIST_DIR / "Cashier Mode.exe",
        DIST_DIR / "Cashier_Mode.exe",
        DIST_DIR / "CashierMode.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    matches = sorted(DIST_DIR.glob("*Cashier*.exe"))
    if matches:
        return matches[0]

    raise FileNotFoundError(
        "Cashier Mode EXE was not found in dist. Run build_cashier_exe.py first."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    exe_path = find_cashier_exe()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / f"Cashier_Mode_v{args.version}.zip"

    readme = (
        f"ZAY POS Cashier Mode v{args.version}\n\n"
        "Place Cashier Mode.exe in the same installed ZAY POS folder so it can "
        "use the existing database, assets, and runtime files.\n"
    )

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe_path, "Cashier Mode.exe")
        archive.writestr("README.txt", readme)

    print(f"Cashier package created: {zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
