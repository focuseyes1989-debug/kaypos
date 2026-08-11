"""Matplotlib font helpers for Myanmar text rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
import matplotlib.font_manager as fm

_CONFIGURED_FAMILY: Optional[str] = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _candidate_font_paths() -> list[Path]:
    fonts_dir = _project_root() / "assets" / "fonts"
    return [
        fonts_dir / "mmrtext.ttf",
        fonts_dir / "NotoSansMyanmar-Regular.ttf",
        fonts_dir / "mmrtextb.ttf",
        fonts_dir / "NotoSansMyanmar-Bold.ttf",
        Path("C:/Windows/Fonts/mmrtext.ttf"),
        Path("C:/Windows/Fonts/MyanmarText.ttf"),
        Path("C:/Windows/Fonts/NotoSansMyanmar-Regular.ttf"),
        Path("C:/Windows/Fonts/Pyidaungsu.ttf"),
    ]


def configure_myanmar_matplotlib_font() -> str:
    """Register and select a Myanmar-capable font for Matplotlib charts."""
    global _CONFIGURED_FAMILY

    if _CONFIGURED_FAMILY:
        return _CONFIGURED_FAMILY

    selected_family: Optional[str] = None

    for font_path in _candidate_font_paths():
        if not font_path.exists():
            continue
        try:
            fm.fontManager.addfont(str(font_path))
            selected_family = fm.FontProperties(fname=str(font_path)).get_name()
            break
        except Exception:
            continue

    if not selected_family:
        selected_family = "Myanmar Text"

    available_families = {font.name for font in fm.fontManager.ttflist}
    font_stack = [selected_family]
    for family in ["Myanmar Text", "Noto Sans Myanmar", "Pyidaungsu", "Segoe UI", "Arial", "DejaVu Sans"]:
        if family in available_families and family not in font_stack:
            font_stack.append(family)
    matplotlib.rcParams["font.family"] = font_stack
    matplotlib.rcParams["font.sans-serif"] = font_stack
    matplotlib.rcParams["font.size"] = 9
    matplotlib.rcParams["font.weight"] = "normal"
    matplotlib.rcParams["axes.titleweight"] = "normal"
    matplotlib.rcParams["axes.labelweight"] = "normal"
    matplotlib.rcParams["axes.unicode_minus"] = False

    _CONFIGURED_FAMILY = selected_family
    return selected_family


def get_myanmar_font_properties(size: int = 10, weight: str = "normal") -> fm.FontProperties:
    """Return FontProperties using the configured Myanmar-capable family."""
    family = configure_myanmar_matplotlib_font()
    return fm.FontProperties(family=family, size=size, weight=weight)
