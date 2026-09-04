"""Static inventory only: no application imports, database access, or network calls.
Run from the repository root: python docs/native_phase1/generate_inventory.py
"""
import ast
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
AREAS = ('ui', 'app', 'core', 'models', 'services', 'utils', 'server', 'lite_pos', 'service_job_client', 'car_client')
files, classes, shortcuts, dependencies, errors = [], [], [], [], []
for area in AREAS:
    for path in sorted((ROOT / area).rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        relative = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding='utf-8-sig')
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            errors.append({'path': relative, 'line': exc.lineno, 'error': exc.msg})
            continue
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add('.' * node.level + (node.module or ''))
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(base) for base in node.bases]
                classes.append({'path': relative, 'line': node.lineno, 'class': node.name, 'bases': '; '.join(bases), 'dialog_candidate': 'yes' if 'Dialog' in node.name or any('QDialog' in base for base in bases) else 'no'})
            elif isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.endswith(('setShortcut', 'QShortcut', 'QKeySequence', '_add_shortcut')):
                    shortcuts.append({'path': relative, 'line': node.lineno, 'expression': ast.unparse(node)})
        for module in sorted(imports):
            dependencies.append({'path': relative, 'import': module})
        files.append({'path': relative, 'lines': len(source.splitlines()),
            'stylesheet_calls': source.count('.setStyleSheet('),
            'paint_event_definitions': source.count('def paintEvent('),
            'theme_dependency': any('theme' in module or 'design_system' in module for module in imports),
            'database_dependency': any('database' in module for module in imports),
            'qt_dependency': any('PyQt6' in module for module in imports),
            'sql_execute_calls': source.count('.execute('),
            'imports_ui': any(module == 'ui' or module.startswith('ui.') for module in imports)})

def write_csv(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ['path'])
        writer.writeheader()
        writer.writerows(rows)
write_csv('files.csv', files)
write_csv('classes.csv', classes)
write_csv('shortcuts.csv', shortcuts)
write_csv('imports.csv', dependencies)
ui = [row for row in files if row['path'].startswith('ui/')]
summary = {
    'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'scope': list(AREAS), 'source': 'current working tree; static evidence, not runtime coverage',
    'files': len(files), 'ui_files': len(ui), 'ui_lines': sum(row['lines'] for row in ui),
    'ui_files_with_stylesheet_calls': sum(row['stylesheet_calls'] > 0 for row in ui),
    'ui_stylesheet_calls_textual': sum(row['stylesheet_calls'] for row in ui),
    'ui_files_with_database_imports': sum(row['database_dependency'] for row in ui),
    'ui_dialog_candidates': sum(row['path'].startswith('ui/') and row['dialog_candidate'] == 'yes' for row in classes),
    'ui_paint_event_definitions_textual': sum(row['paint_event_definitions'] for row in ui),
    'parse_errors': errors,
    'limitations': ['Textual counts can include comments and are not executed-call counts.',
                   'Dialog candidates are class-name/base heuristics, not unique reachable dialogs.',
                   'Imports include conditional/lazy imports, not proof of runtime reachability.',
                   'Root entry points and launcher were reviewed manually; runtime data and static web assets excluded.']}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
