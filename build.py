# build.py
"""
Build script for ZAY POS with interactive version input and launcher support.
Fixed launcher and main app in same folder.
"""

import os
import sys
import shutil
import subprocess
import re
import site
from pathlib import Path
from datetime import datetime

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Default version (will be overwritten by user input)
APP_VERSION = "1.5.9"
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
    
    return version

def clean_build():
    """Clean build directories."""
    print("\n🧹 Cleaning build directories...")
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ Removed: {dir_name}")
    
    for file in Path('.').glob('*.spec'):
        file.unlink()
        print(f"✅ Removed: {file}")

def create_dist_folder(version):
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
    
    print(f"✅ Distribution folder structure created: {dist_folder}")

def copy_assets(version):
    """Copy assets to dist folder."""
    dist_folder = Path(f'dist/{APP_NAME}_v{version}')
    
    if os.path.exists('assets'):
        shutil.copytree('assets', dist_folder / 'assets', dirs_exist_ok=True)
        print("✅ Assets copied")

def build_exe(version):
    """Build executable with PyInstaller."""
    print(f"\n🚀 Building ZAY POS v{version}...")
    
    # Clean dist folder
    if os.path.exists('dist'):
        shutil.rmtree('dist')
        print("✅ Cleaned dist folder")
    
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
            
            # Move to versioned folder
            dist_folder = Path('dist')
            old_name = dist_folder / APP_NAME
            new_name = dist_folder / f'{APP_NAME}_v{version}'
            
            if old_name.exists():
                if new_name.exists():
                    shutil.rmtree(new_name)
                old_name.rename(new_name)
                print(f"✅ Renamed to: {APP_NAME}_v{version}")
            
            return True
        else:
            print(f"❌ Build failed: {result.stderr}")
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ Build failed: {e}")
        return False

def build_launcher(version):
    """Build the launcher executable and place in same folder as main app."""
    print(f"\n🚀 Building Launcher v{version}...")
    
    if not os.path.exists('launcher.py'):
        print("⚠️ launcher.py not found, skipping launcher build")
        return False
    
    # 🔥 Get the versioned folder path
    versioned_folder = Path(f'dist/{APP_NAME}_v{version}')
    versioned_folder.mkdir(parents=True, exist_ok=True)
    version_txt_path = os.path.abspath('version.txt')
    icon_path = os.path.abspath('assets/icons/app_icon.ico')
    
    print(f"📂 Target folder: {versioned_folder}")
    
    # Check if launcher.py has syntax errors
    print("🔍 Checking launcher.py syntax...")
    try:
        import py_compile
        py_compile.compile('launcher.py', doraise=True)
        print("✅ launcher.py syntax OK")
    except py_compile.PyCompileError as e:
        print(f"❌ launcher.py has syntax error: {e}")
        return False
    
    # 🔥 Build launcher directly into versioned folder
    # Use --distpath to put launcher directly in versioned folder
    launcher_cmd = [
        sys.executable,
        '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        f'--distpath={versioned_folder}',  # 🔥 Direct to versioned folder
        f'--workpath=build/launcher',
        f'--specpath=build/launcher',
        '--name=ZAY_POS_Launcher',  # 🔥 Name for the exe
        f'--icon={icon_path}',
        f'--add-data={version_txt_path};.',
        # PyQt6
        '--hidden-import=PyQt6',
        '--hidden-import=PyQt6.QtWidgets',
        '--hidden-import=PyQt6.QtGui',
        '--hidden-import=PyQt6.QtCore',
        # Requests - Full import
        '--hidden-import=requests',
        '--hidden-import=requests.models',
        '--hidden-import=requests.api',
        '--hidden-import=requests.sessions',
        '--hidden-import=requests.adapters',
        '--hidden-import=requests.auth',
        '--hidden-import=requests.cookies',
        '--hidden-import=requests.exceptions',
        '--hidden-import=requests.hooks',
        '--hidden-import=requests.status_codes',
        '--hidden-import=requests.structures',
        '--hidden-import=requests.utils',
        # urllib3
        '--hidden-import=urllib3',
        '--hidden-import=urllib3.poolmanager',
        '--hidden-import=urllib3.response',
        # Common
        '--hidden-import=json',
        '--hidden-import=zipfile',
        '--hidden-import=shutil',
        '--hidden-import=tempfile',
        '--hidden-import=hashlib',
        '--hidden-import=re',
        '--hidden-import=subprocess',
        '--hidden-import=threading',
        '--hidden-import=datetime',
        '--hidden-import=typing',
        '--hidden-import=pathlib',
        # Exclude tkinter
        '--exclude-module=tkinter',
        '--exclude-module=_tkinter',
        '--exclude-module=tcl',
        '--exclude-module=tk',
        'launcher.py'
    ]
    
    # Add site-packages to path
    try:
        site_packages = site.getsitepackages()
        for path in site_packages:
            if os.path.exists(path):
                launcher_cmd.append(f'--paths={path}')
    except:
        pass
    
    try:
        print("📝 Running PyInstaller for launcher...")
        result = subprocess.run(launcher_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Launcher build successful!")
            
            # 🔥 Check if launcher was created in versioned folder
            launcher_exe = versioned_folder / 'ZAY_POS_Launcher.exe'
            
            if launcher_exe.exists():
                print(f"✅ Launcher EXE created: {launcher_exe}")
                print(f"📁 Size: {launcher_exe.stat().st_size // 1024} KB")
            else:
                # 🔥 Maybe it created a folder with the exe inside
                launcher_folder = versioned_folder / 'ZAY_POS_Launcher'
                if launcher_folder.exists():
                    print(f"📂 Found launcher folder: {launcher_folder}")
                    
                    # Move all files from launcher folder to root
                    for item in launcher_folder.iterdir():
                        dest = versioned_folder / item.name
                        if dest.exists():
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(str(item), str(dest))
                    
                    # Remove empty launcher folder
                    launcher_folder.rmdir()
                    print(f"✅ Launcher files moved to root: {versioned_folder}")
                    
                    # Verify again
                    if launcher_exe.exists():
                        print(f"✅ Launcher EXE confirmed: {launcher_exe}")
                    else:
                        print(f"⚠️ Launcher EXE still not found: {launcher_exe}")
                        # 🔥 Try to find and copy from build folder
                        self._find_and_copy_launcher(version)
                else:
                    print(f"⚠️ Launcher folder not found: {launcher_folder}")
                    # 🔥 Try to find and copy from build folder
                    self._find_and_copy_launcher(version)
            
            return True
        else:
            print(f"❌ Launcher build failed (return code: {result.returncode})")
            if result.stderr:
                print(f"Error: {result.stderr}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Launcher build failed: {e}")
        return False

def _find_and_copy_launcher(self, version):
    """Try to find launcher in build folder and copy it."""
    versioned_folder = Path(f'dist/{APP_NAME}_v{version}')
    
    # Check build/launcher folder
    build_launcher = Path('build/launcher/ZAY_POS_Launcher.exe')
    if build_launcher.exists():
        dest = versioned_folder / 'ZAY_POS_Launcher.exe'
        shutil.copy2(build_launcher, dest)
        print(f"✅ Copied launcher from build folder: {dest}")
        return
    
    # Check dist folder for any launcher
    for exe in Path('dist').rglob('ZAY_POS_Launcher.exe'):
        if exe.parent != versioned_folder:
            dest = versioned_folder / 'ZAY_POS_Launcher.exe'
            shutil.copy2(exe, dest)
            print(f"✅ Copied launcher from: {exe} → {dest}")
            return
    
    print("⚠️ Could not find launcher executable anywhere")

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
2. Run ZAY_POS_Launcher.exe (recommended) or ZAY_POS.exe

⚠️ Important:
- Both EXE files must be in the same folder
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
- ZAY_POS_Launcher.exe

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

def print_summary(version, zip_name):
    """Print build summary."""
    print("\n" + "=" * 60)
    print("✅ BUILD COMPLETE!")
    print("=" * 60)
    print(f"\n📌 Version: {version}")
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
                print(f"   - {item.name} ({size} KB)")
            else:
                print(f"   - {item.name}/ (folder)")
    
    print("\n📝 Run from:")
    print(f"   - Recommended: ZAY_POS_Launcher.exe")
    print(f"   - Direct: {APP_NAME}.exe")
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
    print("🏗️  ZAY POS BUILD SYSTEM")
    print("=" * 60)
    
    version = get_version_input()
    global APP_VERSION
    APP_VERSION = version
    
    print(f"\n📌 Building version: {APP_VERSION}")
    print("=" * 60)
    
    update_version_in_files(version)
    clean_build()
    
    # Build main app
    if not build_exe(version):
        print("\n❌ Build failed! Please check the error above.")
        sys.exit(1)
    
    # Create dist structure
    create_dist_folder(version)
    
    # Copy assets
    copy_assets(version)
    
    # Build launcher (puts in same folder)
    if not build_launcher(version):
        print("\n❌ Launcher build failed! Please check the error above.")
        sys.exit(1)
    
    # Create antivirus info
    create_antivirus_info(version)
    
    # Create release zip
    zip_name = create_release_zip(version)
    
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
