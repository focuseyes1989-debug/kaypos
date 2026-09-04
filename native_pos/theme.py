"""Standard Qt styles and palettes. No application stylesheet or custom painting."""
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QStyleFactory

class NativeTheme:
    def __init__(self, app):
        self.app = app
        self.system_style = app.style().objectName()
        self.system_palette = QPalette(app.palette())
        self.system_font = QFont(app.font())

    def apply(self, config):
        available = {name.casefold(): name for name in QStyleFactory.keys()}
        style_name = config.get('style', 'System')
        requested = self.system_style if style_name == 'System' else style_name
        palette_name = config.get('palette', 'System')
        # Fusion reliably observes explicit palettes; OS styles may ignore them.
        if palette_name in ('Light', 'Dark') and 'fusion' in available:
            requested = 'Fusion'
        selected = available.get(requested.casefold()) or available.get('fusion')
        if selected:
            self.app.setStyle(QStyleFactory.create(selected))
        palette = QPalette(self.system_palette) if palette_name == 'System' else self.app.style().standardPalette()
        if palette_name == 'Dark':
            colors = {
                'Window':'#242424','WindowText':'#eeeeee','Base':'#191919','AlternateBase':'#303030',
                'Text':'#eeeeee','Button':'#303030','ButtonText':'#eeeeee','Highlight':'#3976ba',
                'HighlightedText':'#ffffff','ToolTipBase':'#303030','ToolTipText':'#eeeeee',
                'Link':'#80baff','PlaceholderText':'#aaaaaa',
            }
            for role, value in colors.items():
                palette.setColor(getattr(QPalette.ColorRole,role),QColor(value))
            for role in (QPalette.ColorRole.Text,QPalette.ColorRole.WindowText,QPalette.ColorRole.ButtonText):
                palette.setColor(QPalette.ColorGroup.Disabled,role,QColor('#929292'))
        self.app.setPalette(palette)
        font = QFont(self.system_font)
        if config.get('font_family'):
            font.setFamily(config['font_family'])
        font.setPointSize(int(config.get('font_size',10)))
        self.app.setFont(font)
        return self.app.style().objectName()
