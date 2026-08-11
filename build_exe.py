# build_exe.py
"""
Build script for ZAY POS EXE only.
Builds main application executable with interactive version input.
"""

import os
import sys
import shutil
import subprocess
import re
from pathlib import Path
from datetime import datetime

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Default version
APP_VERSION = "1.0.0"
APP_NAME = "ZAY_POS"

def get_version_input():
    """Get version from user input with validation."""
    print("\n" + "=" * 60)
    print("🔢 ENTER VERSION NUMBER")
    print("=" * 60)
    print("Current version: 1.0.7")
    print("Format: x.y.z (e.g., 1.0.8, 1.1.0, 2.0.0)")
    print("-" * 60)
    
    while True:
        version = input("Enter version: ").strip()
        
        if not version:
            version = "1.0.7"
            print(f"📌 Using default version: {version}")
            return version
        
        if re.match(r'^\d+\.\d+\.\d+$', version):
            return version
        else:
            print("❌ Invalid version format! Please use format: x.y.z (e.g., 1.0.8)")
            continue

def update_version_in_files(version):
    """Update version in all relevant files."""
    print(f"\n📝 Updating version to: {version}")
    
    # Update version.txt
    version_content = f"""
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version.replace('.', ', ')}, 0),
    prodvers=({version.replace('.', ', ')}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u'ZAY POS'),
            StringStruct(u'FileDescription', u'ZAY POS Application'),
            StringStruct(u'FileVersion', u'{version}'),
            StringStruct(u'InternalName', u'ZAY_POS'),
            StringStruct(u'LegalCopyright', u'ZAY POS'),
            StringStruct(u'OriginalFilename', u'ZAY_POS.exe'),
            StringStruct(u'ProductName', u'ZAY POS'),
            StringStruct(u'ProductVersion', u'{version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    with open('version.txt', 'w', encoding='utf-8') as f:
        f.write(version_content)
    print("✅ Updated: version.txt")
    
    # Update build.py APP_VERSION if exists
    build_py_path = Path('build.py')
    if build_py_path.exists():
        try:
            with open(build_py_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content = re.sub(
                r'APP_VERSION\s*=\s*["\']([\d.]+)["\']',
                f'APP_VERSION = "{version}"',
                content
            )
            with open(build_py_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("✅ Updated: build.py")
        except Exception as e:
            print(f"⚠️ Could not update build.py: {e}")
    
    return version

def clean_build():
    """Clean build directories."""
    print("\n🧹 Cleaning build directories...")
    dirs_to_clean = ['build', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ Removed: {dir_name}")
    
    # Clean .spec files
    for file in Path('.').glob('*.spec'):
        file.unlink()
        print(f"✅ Removed: {file}")

def build_exe(version):
    """Build executable with PyInstaller."""
    print(f"\n🚀 Building ZAY POS v{version}...")
    
    # Clean dist folder for ZAY_POS
    if os.path.exists('dist'):
        # Only remove ZAY_POS folder, not versioned folders
        for item in Path('dist').iterdir():
            if item.name == APP_NAME or item.name == f'{APP_NAME}.exe':
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                print(f"✅ Removed: {item}")
    
    # Check if icon exists
    icon_path = "assets/icons/app_icon.ico"
    if not os.path.exists(icon_path):
        print(f"⚠️ Icon not found: {icon_path}")
        icon_path = "NONE"
    
# Create spec file
    spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

import os
import sys


sqlite_binaries = []
python_dll_dir = os.path.join(sys.base_prefix, 'DLLs')
for sqlite_name in ('_sqlite3.pyd', 'sqlite3.dll'):
    sqlite_path = os.path.join(python_dll_dir, sqlite_name)
    if os.path.exists(sqlite_path):
        sqlite_binaries.append((sqlite_path, '.'))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=sqlite_binaries,
    datas=[
        ('assets', 'assets'),
        ('qt.conf', '.'),
        ('version.txt', '.'),
        ('updater/version_manager.py', 'updater'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.QtCore',
        'PyQt6.QtPrintSupport',
        'PyQt6.QtSql',
        'loguru',
        'sqlite3',
        '_sqlite3',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.figure',
        'matplotlib.backends',
        'matplotlib.backends.backend_qtagg',
        'matplotlib.font_manager',
        'matplotlib.text',
        'matplotlib.colors',
        'matplotlib.lines',
        'matplotlib.patches',
        'matplotlib.axes',
        'matplotlib.axis',
        'matplotlib.ticker',
        'matplotlib.scale',
        'matplotlib.transforms',
        'matplotlib.path',
        'matplotlib.cm',
        'matplotlib.collections',
        'matplotlib.image',
        'matplotlib.legend',
        'matplotlib.gridspec',
        'matplotlib.dates',
        'matplotlib.backends.backend_agg',
        'numpy',
        'numpy._core',
        'numpy._core._multiarray_umath',
        'numpy._core.umath',
        'numpy._core.multiarray',
        'numpy._core.numeric',
        'numpy._core.fromnumeric',
        'numpy._core.shape_base',
        'numpy._core._internal',
        'numpy._core.arrayprint',
        'numpy._core.defchararray',
        'numpy._core.records',
        'numpy._core.memmap',
        'numpy._core.function_base',
        'numpy._core._dtype',
        'numpy._core._methods',
        'numpy._core._asarray',
        'numpy._core._ufunc_config',
        'numpy._core._type_aliases',
        'numpy._core._string_helpers',
        'numpy._core._exceptions',
        'numpy.version',
        'numpy._globals',
        'numpy._distributor_init',
        'numpy._typing',
        'numpy._typing._array_like',
        'numpy._typing._dtype_like',
        'numpy._typing._scalars',
        'numpy._typing._shape',
        'numpy._typing._ufunc',
        'PIL',
        'PIL.Image',
        'PIL.ImageQt',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'json',
        'hashlib',
        'subprocess',
        'threading',
        'datetime',
        'typing',
        'collections',
        'io',
        're',
        'time',
        'shutil',
        'os',
        'sys',
        'warnings',
        'traceback',
        'ctypes',
        'struct',
        'updater.version_manager',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'tcl',
        'tk',
        'test',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
        'matplotlib.tests',
        'setuptools',
        'pkg_resources',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    exclude_binaries=True,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}' if '{icon_path}' != "NONE" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='{APP_NAME}',
)
'''
    
    spec_file = f'{APP_NAME}.spec'
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"✅ Created spec file: {spec_file}")
    
    cmd = [
        sys.executable,
        '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        spec_file
    ]
    
    print(f"📝 Running PyInstaller with spec file...")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Build successful!")
            
            # 🔥 Create versioned folder and move files
            dist_folder = Path('dist')
            old_name = dist_folder / APP_NAME
            new_name = dist_folder / f'{APP_NAME}_v{version}'
            
            if old_name.exists():
                # Remove existing versioned folder if exists
                if new_name.exists():
                    shutil.rmtree(new_name)
                # Rename to versioned folder
                old_name.rename(new_name)
                print(f"✅ Created: {APP_NAME}_v{version}")
                
                # 🔥 Also copy assets and create folders
                create_dist_folders(version)
                copy_assets(version)
                
                return True
            else:
                # Check if exe is directly in dist
                exe_path = dist_folder / f'{APP_NAME}.exe'
                if exe_path.exists():
                    # Create versioned folder
                    new_name.mkdir(parents=True, exist_ok=True)
                    # Move exe to versioned folder
                    shutil.move(str(exe_path), str(new_name / exe_path.name))
                    print(f"✅ Moved EXE to: {APP_NAME}_v{version}")
                    
                    create_dist_folders(version)
                    copy_assets(version)
                    return True
                else:
                    print("⚠️ Could not find built executable")
                    return False
        else:
            print(f"❌ Build failed: {result.stderr}")
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ Build failed: {e}")
        return False

def create_dist_folders(version):
    """Create distribution folder structure."""
    dist_folder = Path(f'dist/{APP_NAME}_v{version}')
    dist_folder.mkdir(parents=True, exist_ok=True)
    
    # Create necessary folders
    folders = ['database', 'logs', 'temp']
    for folder in folders:
        (dist_folder / folder).mkdir(exist_ok=True)
        
        if folder == 'database':
            (dist_folder / folder / '.gitkeep').touch()
            (dist_folder / folder / 'product_images').mkdir(exist_ok=True)
            (dist_folder / folder / 'product_images' / '.gitkeep').touch()
            (dist_folder / folder / 'backups').mkdir(exist_ok=True)
            (dist_folder / folder / 'backups' / '.gitkeep').touch()
    
    print(f"✅ Distribution folders created: {dist_folder}")

def copy_assets(version):
    """Copy assets to dist folder."""
    dist_folder = Path(f'dist/{APP_NAME}_v{version}')
    
    if os.path.exists('assets'):
        shutil.copytree('assets', dist_folder / 'assets', dirs_exist_ok=True)
        print("✅ Assets copied")

def create_antivirus_info(version):
    """Create antivirus whitelist information."""
    info_content = f"""
========================================
ZAY POS v{version} - Antivirus False Positive Fix
========================================

If your antivirus detects ZAY_POS.exe as a threat,
please add it to your antivirus whitelist.

Files to whitelist:
- ZAY_POS.exe

How to whitelist:

1. Windows Defender:
   - Open Windows Security
   - Go to Virus & threat protection
   - Click "Manage settings"
   - Scroll to "Exclusions"
   - Add the entire ZAY_POS_v{version} folder

2. Other Antivirus:
   - Open your antivirus settings
   - Find "Exclusions" or "Whitelist"
   - Add the ZAY_POS.exe file

========================================
"""
    app_folder = Path(f'dist/{APP_NAME}_v{version}')
    if app_folder.exists():
        with open(app_folder / 'WHITELIST_INFO.txt', 'w') as f:
            f.write(info_content)
        print("✅ Whitelist info created")

def create_release_zip(version):
    """Create release zip file with version in name."""
    import zipfile
    
    zip_name = f'{APP_NAME}_v{version}.zip'
    dist_folder = Path('dist')
    app_folder = dist_folder / f'{APP_NAME}_v{version}'
    
    if not app_folder.exists():
        print(f"⚠️ Application folder not found: {app_folder}")
        return None
    
    print(f"\n📦 Creating release zip: {zip_name}")
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in app_folder.rglob('*'):
            if file.is_file():
                arcname = str(file.relative_to(dist_folder))
                zipf.write(file, arcname)
                print(f"✅ Added: {arcname}")
        
        readme_content = f"""
ZAY POS Installation
====================

Version: {version}
Date: {datetime.now().strftime('%Y-%m-%d')}

1. Extract the zip file to a folder
2. Run ZAY_POS.exe

⚠️ Important:
- Database files will be created on first run
- Default Login: admin / admin

System Requirements:
- Windows 7 or later
- 2GB RAM minimum
- 100MB free disk space

Changelog:
- Version {version}
"""
        zipf.writestr('README.txt', readme_content)
        print("✅ Added: README.txt")
    
    print(f"✅ Release zip created: {zip_name}")
    return zip_name

def print_summary(version, zip_name):
    """Print build summary."""
    print("\n" + "=" * 60)
    print("✅ BUILD COMPLETE!")
    print("=" * 60)
    print(f"\n📌 Version: {version}")
    
    if zip_name:
        print(f"📁 Release file: {zip_name}")
        print(f"📁 Location: {os.path.abspath(zip_name)}")
    
    print(f"\n📁 Application folder: dist/{APP_NAME}_v{version}/")
    print("\n📝 Files in folder:")
    
    # Show actual files
    app_folder = Path(f'dist/{APP_NAME}_v{version}')
    if app_folder.exists():
        for item in app_folder.iterdir():
            if item.is_file():
                size = item.stat().st_size // 1024
                if size > 1024:
                    size = f"{size // 1024} MB"
                else:
                    size = f"{size} KB"
                print(f"   - {item.name} ({size})")
            else:
                print(f"   - {item.name}/ (folder)")
    
    print("\n📝 Run from:")
    print(f"   - {APP_NAME}.exe")
    print("\n📝 Antivirus Tips:")
    print("   - If antivirus flags the app, add to whitelist")
    print("   - See WHITELIST_INFO.txt for instructions")
    print("\n📝 Default Login:")
    print("   - Username: admin")
    print("   - Password: admin")
    print("=" * 60)

def main():
    """Main build process."""
    print("=" * 60)
    print("🏗️  ZAY POS EXE BUILDER")
    print("=" * 60)
    
    version = get_version_input()
    global APP_VERSION
    APP_VERSION = version
    
    print(f"\n📌 Building version: {APP_VERSION}")
    print("=" * 60)
    
    # Update version in files
    update_version_in_files(version)
    
    # Clean build
    clean_build()
    
    # Build main app
    if not build_exe(version):
        print("\n❌ Build failed! Please check the error above.")
        sys.exit(1)
    
    # Create antivirus info
    create_antivirus_info(version)
    
    # Create release zip
    zip_name = create_release_zip(version)
    
    # Print summary
    print_summary(version, zip_name)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
