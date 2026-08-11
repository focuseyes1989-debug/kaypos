from pathlib import Path
path = Path('ui/sales_page/checkout_handler/checkout_handler.py')
text = path.read_text(encoding='utf-8')
text = text.replace('self.parent = parent', 'self.parent_widget = parent')
text = text.replace('self.parent.', 'self.parent_widget.')
path.write_text(text, encoding='utf-8')
print('updated checkout handler')
