"""Category badge colors matching Touch POS categoryTone and its CSS palette."""

LIGHT = (
    ("#dbeafe", "#1e40af"), ("#d1fae5", "#065f46"),
    ("#ede9fe", "#5b21b6"), ("#fef3c7", "#92400e"),
    ("#fce7f3", "#9d174d"), ("#cffafe", "#155e75"),
)
DARK = (
    ("#1e3a5f", "#bfdbfe"), ("#134e4a", "#a7f3d0"),
    ("#3b2763", "#ddd6fe"), ("#593c18", "#fde68a"),
    ("#57233e", "#fbcfe8"), ("#164e63", "#a5f3fc"),
)


def category_badge_colors(category, dark=False):
    value = 0
    for char in str(category or "No category").strip().lower():
        value = (value * 31 + ord(char)) & 0xffffffff
    return (DARK if dark else LIGHT)[value % 6]
