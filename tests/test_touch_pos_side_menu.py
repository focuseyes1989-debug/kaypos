"""Touch POS side menu tests."""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "server" / "static" / "touch_pos"


class TouchPosSideMenuTests(unittest.TestCase):
    def test_header_has_side_menu_button_before_logo(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        button_index = html.index('id="sideMenuButton"')
        logo_index = html.index('src="/assets/kay/kay_128x128.png"', html.index('<header class="topbar">'))
        self.assertLess(button_index, logo_index)
        self.assertIn('id="sideMenu"', html)
        self.assertIn('id="sideMenuOverlay"', html)

    def test_side_menu_slides_from_top_left(self):
        css = (STATIC / "touch-pos.css").read_text(encoding="utf-8")
        self.assertIn(".side-menu{", css)
        self.assertIn("top:0;", css)
        self.assertIn("left:0;", css)
        self.assertIn("transform:translate(-110%,0)", css)
        self.assertIn(".side-menu-section", css)
        self.assertIn("background:#ff5a2c", css)
        self.assertIn(".side-menu.open", css)

    def test_side_menu_is_interactive(self):
        script = (STATIC / "touch-pos.js").read_text(encoding="utf-8")
        self.assertIn("function setSideMenuOpen", script)
        self.assertIn("sideMenuButton.addEventListener('click'", script)
        self.assertIn("sideMenuOverlay.addEventListener('click'", script)
        self.assertIn("data-side-action", script)


if __name__ == "__main__":
    unittest.main()
