# ui/responsive_utils.py
"""Helpers for keeping the UI usable on smaller laptop displays."""

from typing import List, Tuple


def get_responsive_window_size(
    screen_width: int,
    screen_height: int,
    preferred_width: int = 1366,
    preferred_height: int = 768,
    min_width: int = 1024,
    min_height: int = 600,
) -> Tuple[int, int]:
    """Return a window size that fits comfortably on the current screen."""
    if screen_width <= 0 or screen_height <= 0:
        return preferred_width, preferred_height

    # 90% of screen size (with margin)
    width = min(int(screen_width * 0.9), preferred_width)
    height = min(int(screen_height * 0.9), preferred_height)

    # Ensure minimum size
    width = max(width, min_width)
    height = max(height, min_height)

    # Never exceed screen size
    if width > screen_width:
        width = screen_width
    if height > screen_height:
        height = screen_height

    return width, height


def get_supported_resolution_options(
    screen_width: int,
    screen_height: int,
    min_width: int = 1366,
    min_height: int = 768,
) -> List[Tuple[str, int, int]]:
    """Return common app window resolutions that fit the available screen."""
    presets = [
        (1366, 768),
        (1440, 900),
        (1600, 900),
        (1680, 1050),
        (1920, 1080),
        (2560, 1440),
        (3840, 2160),
    ]

    if screen_width > 0 and screen_height > 0:
        presets.append((screen_width, screen_height))

    options = []
    seen = set()
    for width, height in presets:
        if width < min_width or height < min_height:
            continue
        if screen_width > 0 and height > screen_height:
            continue
        if screen_height > 0 and width > screen_width:
            continue
        if (width, height) in seen:
            continue
        seen.add((width, height))
        label = f"{width}x{height}"
        if width == screen_width and height == screen_height:
            label += " (Max)"
        options.append((label, width, height))

    if not options:
        width = max(min_width, min(screen_width or min_width, min_width))
        height = max(min_height, min(screen_height or min_height, min_height))
        options.append((f"{width}x{height}", width, height))

    return options


def parse_resolution(value: str, fallback_width: int = 1366, fallback_height: int = 768) -> Tuple[int, int]:
    """Parse a saved resolution string such as 1366x768."""
    try:
        width_text, height_text = (value or "").lower().split("x", 1)
        width = int(width_text.strip())
        height = int(height_text.strip())
        if width > 0 and height > 0:
            return width, height
    except Exception:
        pass
    return fallback_width, fallback_height


def get_responsive_dialog_size(
    screen_width: int,
    screen_height: int,
    preferred_width: int = 860,
    preferred_height: int = 520,
    min_width: int = 720,
    min_height: int = 460,
) -> Tuple[int, int]:
    """Return a dialog size that fits comfortably on the current screen."""
    if screen_width <= 0 or screen_height <= 0:
        return preferred_width, preferred_height

    width = min(int(screen_width * 0.65), preferred_width)
    height = min(int(screen_height * 0.72), preferred_height)

    width = max(width, min_width)
    height = max(height, min_height)

    if width > screen_width:
        width = screen_width
    if height > screen_height:
        height = screen_height

    return width, height


def get_responsive_font_size(
    window_width: int,
    base_size: int = 10,
    min_size: int = 8,
    max_size: int = 14,
) -> int:
    """
    Window width အလိုက် font size ကို တွက်ချက်ခြင်း
    
    Args:
        window_width: Window ၏ width
        base_size: Base font size
        min_size: အနည်းဆုံး font size
        max_size: အများဆုံး font size
    
    Returns:
        int: Font size
    """
    if window_width < 1024:
        return min_size
    elif window_width < 1280:
        return base_size
    elif window_width < 1600:
        return base_size + 1
    else:
        return min(max_size, base_size + 2)


def get_responsive_spacing(
    window_width: int,
    base_spacing: int = 8,
    min_spacing: int = 4,
    max_spacing: int = 16,
) -> int:
    """
    Window width အလိုက် spacing ကို တွက်ချက်ခြင်း
    
    Args:
        window_width: Window ၏ width
        base_spacing: Base spacing
        min_spacing: အနည်းဆုံး spacing
        max_spacing: အများဆုံး spacing
    
    Returns:
        int: Spacing
    """
    if window_width < 1024:
        return min_spacing
    elif window_width < 1280:
        return base_spacing
    elif window_width < 1600:
        return base_spacing + 2
    else:
        return min(max_spacing, base_spacing + 4)


def get_responsive_card_size(
    window_width: int,
    min_card_width: int = 110,
    max_card_width: int = 160,
    min_card_height: int = 130,
    max_card_height: int = 185,
) -> Tuple[int, int]:
    """
    Window width အလိုက် product card size ကို တွက်ချက်ခြင်း
    
    Args:
        window_width: Window ၏ width
        min_card_width: အနည်းဆုံး card width
        max_card_width: အများဆုံး card width
        min_card_height: အနည်းဆုံး card height
        max_card_height: အများဆုံး card height
    
    Returns:
        Tuple[int, int]: (card_width, card_height)
    """
    if window_width < 1024:
        card_width = min_card_width
    elif window_width < 1280:
        card_width = int((min_card_width + max_card_width) / 2)
    elif window_width < 1600:
        card_width = max_card_width - 10
    else:
        card_width = max_card_width
    
    card_height = int(card_width * 1.15)
    card_height = max(min_card_height, min(card_height, max_card_height))
    
    return card_width, card_height


def get_responsive_columns(
    window_width: int,
    available_width: int,
    card_width: int,
    min_spacing: int = 4,
    max_spacing: int = 16,
) -> int:
    """
    Window width အလိုက် columns အရေအတွက်ကို တွက်ချက်ခြင်း
    
    Args:
        window_width: Window ၏ width
        available_width: ရရှိနိုင်သော width
        card_width: Card တစ်ခု၏ width
        min_spacing: အနည်းဆုံး spacing
        max_spacing: အများဆုံး spacing
    
    Returns:
        int: Columns အရေအတွက်
    """
    spacing = get_responsive_spacing(window_width, min_spacing=min_spacing, max_spacing=max_spacing)
    item_width = card_width + spacing
    
    if item_width <= 0:
        return 1
    
    cols = max(1, available_width // item_width)
    
    # Minimum columns based on window size
    if window_width >= 1920:
        return max(cols, 6)
    elif window_width >= 1600:
        return max(cols, 5)
    elif window_width >= 1280:
        return max(cols, 4)
    elif window_width >= 1024:
        return max(cols, 3)
    else:
        return max(cols, 2)


def get_responsive_padding(
    window_width: int,
    base_padding: int = 16,
    min_padding: int = 8,
    max_padding: int = 24,
) -> int:
    """
    Window width အလိုက် padding ကို တွက်ချက်ခြင်း
    
    Args:
        window_width: Window ၏ width
        base_padding: Base padding
        min_padding: အနည်းဆုံး padding
        max_padding: အများဆုံး padding
    
    Returns:
        int: Padding
    """
    if window_width < 1024:
        return min_padding
    elif window_width < 1280:
        return base_padding
    elif window_width < 1600:
        return base_padding + 4
    else:
        return min(max_padding, base_padding + 8)
