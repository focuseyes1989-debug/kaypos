import os
import re

def find_cursor_in_files(directory):
    cursor_pattern = re.compile(r'cursor\s*:')
    
    for root, dirs, files in os.walk(directory):
        # Skip __pycache__ directories
        if '__pycache__' in root:
            continue
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if cursor_pattern.search(content):
                            print(f"Found cursor in: {filepath}")
                except Exception as e:
                    pass

if __name__ == "__main__":
    find_cursor_in_files("d:\\ZAY_POS_Main")