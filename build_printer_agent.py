"""Build the standalone KAY Printer Agent executable."""

from pathlib import Path

import PyInstaller.__main__


def main() -> int:
    root = Path(__file__).resolve().parent
    PyInstaller.__main__.run([
        str(root / "KAY_Printer_Agent.spec"),
        "--noconfirm",
        "--clean",
        f"--distpath={root / 'dist_printer_agent'}",
        f"--workpath={root / 'build' / 'printer_agent'}",
    ])
    output = root / "dist_printer_agent" / "KAY_Printer_Agent.exe"
    if not output.is_file():
        raise RuntimeError(f"Printer Agent build did not produce {output}")
    print(f"Built: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

