# build_launcher.py
"""
Build script for ZAY POS Launcher only.
Builds launcher.exe and copies to ZAY_POS.exe location.
"""

import os
import sys
import shutil
import subprocess
import site
import re
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

APP_NAME = "ZAY_POS"
LAUNCHER_NAME = "ZAY_POS_Launcher"

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
    """Update version in version.txt."""
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
            StringStruct(u'FileDescription', u'ZAY POS Launcher'),
            StringStruct(u'FileVersion', u'{version}'),
            StringStruct(u'InternalName', u'ZAY_POS_Launcher'),
            StringStruct(u'LegalCopyright', u'ZAY POS'),
            StringStruct(u'OriginalFilename', u'ZAY_POS_Launcher.exe'),
            StringStruct(u'ProductName', u'ZAY POS Launcher'),
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

def find_zay_pos_exe():
    """Find ZAY_POS.exe location."""
    # Check current directory
    if os.path.exists('ZAY_POS.exe'):
        return os.path.abspath('.')
    
    # Check dist folder
    dist_folder = Path('dist')
    if dist_folder.exists():
        for folder in dist_folder.iterdir():
            if folder.is_dir() and folder.name.startswith(APP_NAME):
                exe_path = folder / f'{APP_NAME}.exe'
                if exe_path.exists():
                    return str(folder)
    
    # Check parent directory
    parent = Path('..')
    if (parent / f'{APP_NAME}.exe').exists():
        return str(parent)
    
    return None

def clean_build():
    """Clean build directories."""
    print("\n🧹 Cleaning build directories...")
    dirs_to_clean = ['build', 'dist_launcher', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"✅ Removed: {dir_name}")
    
    for file in Path('.').glob('*.spec'):
        if 'launcher' in file.name.lower():
            file.unlink()
            print(f"✅ Removed: {file}")

def build_launcher(version):
    """Build launcher executable."""
    print("\n" + "=" * 60)
    print("🚀 ZAY POS LAUNCHER BUILDER")
    print("=" * 60)
    print(f"📌 Building version: {version}")
    print("=" * 60)
    
    # Check if launcher.py exists
    if not os.path.exists('launcher.py'):
        print("❌ launcher.py not found!")
        return False
    
    # Find ZAY_POS.exe location
    target_dir = find_zay_pos_exe()
    
    if target_dir:
        print(f"\n📂 Found ZAY_POS.exe in: {target_dir}")
    else:
        print("\n⚠️ ZAY_POS.exe not found!")
        print("📁 Launcher will be built in current directory")
        target_dir = os.getcwd()
    
    print(f"📁 Target directory: {target_dir}")
    
    # Clean build
    clean_build()
    
    # Create output directory
    output_dir = Path('dist_launcher')
    output_dir.mkdir(exist_ok=True)
    
    # 🔥 FIX: Check icon path - use absolute path
    icon_path = os.path.abspath("assets/icons/app_icon.ico")
    if not os.path.exists(icon_path):
        print(f"⚠️ Icon not found: {icon_path}")
        # Try alternative path
        icon_path = os.path.abspath("assets/icons/zaypos.ico")
        if not os.path.exists(icon_path):
            print("⚠️ No icon found, building without icon")
            icon_path = None
    
    if icon_path and os.path.exists(icon_path):
        print(f"✅ Icon found: {icon_path}")
    
    # Check launcher.py syntax
    print("\n🔍 Checking launcher.py syntax...")
    try:
        import py_compile
        py_compile.compile('launcher.py', doraise=True)
        print("✅ launcher.py syntax OK")
    except py_compile.PyCompileError as e:
        print(f"❌ launcher.py has syntax error: {e}")
        return False
    
    # Get absolute path of version.txt
    version_txt_path = os.path.abspath('version.txt')
    if not os.path.exists(version_txt_path):
        print(f"⚠️ version.txt not found at: {version_txt_path}")
        # Create version.txt if not exists
        with open('version.txt', 'w', encoding='utf-8') as f:
            f.write(f'ProductVersion = "{version}"\nFileVersion = "{version}"\n')
        print("✅ Created version.txt")
    
    print(f"📄 Using version.txt from: {version_txt_path}")
    
    # Build command
    cmd = [
        sys.executable,
        '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--clean',
        '--noconfirm',
        f'--distpath={output_dir}',
        f'--workpath=build/launcher',
        f'--specpath=build/launcher',
        f'--name={LAUNCHER_NAME}',
    ]
    
    # 🔥 FIX: Add icon with absolute path
    if icon_path and os.path.exists(icon_path):
        cmd.append(f'--icon={icon_path}')
    
    # Add data files with correct path
    cmd.extend([
        f'--add-data={version_txt_path};.',
        f'--add-data={os.path.abspath("qt.conf")};.',
    ])
    
    # Hidden imports
    hidden_imports = [
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtGui',
        'PyQt6.QtCore',
        'requests',
        'requests.models',
        'requests.api',
        'requests.sessions',
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests.exceptions',
        'requests.hooks',
        'requests.status_codes',
        'requests.structures',
        'requests.utils',
        'urllib3',
        'urllib3.poolmanager',
        'urllib3.response',
        'json',
        'zipfile',
        'shutil',
        'tempfile',
        'hashlib',
        're',
        'subprocess',
        'threading',
        'datetime',
        'typing',
        'pathlib',
    ]
    
    for imp in hidden_imports:
        cmd.append(f'--hidden-import={imp}')
    
    # Exclude modules
    cmd.extend([
        '--exclude-module=tkinter',
        '--exclude-module=_tkinter',
        '--exclude-module=tcl',
        '--exclude-module=tk',
    ])
    
    # Add paths
    cmd.append(f'--paths=.')
    
    # Add launcher.py
    cmd.append('launcher.py')
    
    print("\n📝 Running PyInstaller for launcher...")
    print(f"Command length: {len(cmd)} args")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("\n✅ Launcher build successful!")
            
            # Move launcher files to target directory
            return move_launcher_to_target(output_dir, target_dir)
        else:
            print("\n❌ Launcher build failed!")
            if result.stderr:
                print(f"Error: {result.stderr}")
            if result.stdout:
                print(f"Output: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"\n❌ Launcher build failed: {e}")
        return False

def move_launcher_to_target(output_dir, target_dir):
    """Move launcher files to target directory."""
    print(f"\n📂 Moving launcher to: {target_dir}")
    
    # Find launcher folder or exe
    launcher_folder = output_dir / LAUNCHER_NAME
    launcher_exe = output_dir / f'{LAUNCHER_NAME}.exe'
    
    # If launcher is in folder
    if launcher_folder.exists():
        print(f"📁 Found launcher folder: {launcher_folder}")
        
        # Copy all files from launcher folder to target
        for item in launcher_folder.iterdir():
            dest = Path(target_dir) / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            print(f"✅ Copied: {item.name} → {dest}")
        
        # Remove empty launcher folder
        shutil.rmtree(launcher_folder)
        print("✅ Removed temporary launcher folder")
        
        # Verify launcher exe
        target_exe = Path(target_dir) / f'{LAUNCHER_NAME}.exe'
        if target_exe.exists():
            size = target_exe.stat().st_size // 1024
            print(f"\n✅ Launcher installed successfully!")
            print(f"📁 Location: {target_exe}")
            print(f"📊 Size: {size} KB")
            
            # Clean up
            clean_up_temp_files()
            return True
        else:
            print(f"\n⚠️ Launcher EXE not found in target!")
            return False
    
    # If launcher exe is directly in output_dir
    elif launcher_exe.exists():
        dest = Path(target_dir) / f'{LAUNCHER_NAME}.exe'
        shutil.copy2(launcher_exe, dest)
        size = dest.stat().st_size // 1024
        print(f"\n✅ Launcher installed successfully!")
        print(f"📁 Location: {dest}")
        print(f"📊 Size: {size} KB")
        
        # Clean up
        clean_up_temp_files()
        return True
    
    else:
        print("\n❌ Could not find launcher executable!")
        print(f"   Searched in: {output_dir}")
        print(f"   Looking for: {LAUNCHER_NAME}.exe or {LAUNCHER_NAME}/")
        return False

def clean_up_temp_files():
    """Clean up temporary files."""
    print("\n🧹 Cleaning up temporary files...")
    
    # Remove dist_launcher if empty
    dist_launcher = Path('dist_launcher')
    if dist_launcher.exists():
        try:
            # Check if empty
            if not any(dist_launcher.iterdir()):
                shutil.rmtree(dist_launcher)
                print("✅ Removed empty dist_launcher folder")
        except:
            pass
    
    # Remove build/launcher if exists
    build_launcher = Path('build/launcher')
    if build_launcher.exists():
        try:
            shutil.rmtree(build_launcher)
            print("✅ Removed build/launcher folder")
        except:
            pass

def print_summary(target_dir, version):
    """Print build summary."""
    print("\n" + "=" * 60)
    print("✅ BUILD COMPLETE!")
    print("=" * 60)
    
    target_exe = Path(target_dir) / f'{LAUNCHER_NAME}.exe'
    main_exe = Path(target_dir) / f'{APP_NAME}.exe'
    
    print(f"\n📌 Version: {version}")
    print(f"📁 Target folder: {target_dir}")
    print("\n📝 Files in folder:")
    
    # List files in target
    if Path(target_dir).exists():
        for item in Path(target_dir).iterdir():
            if item.is_file():
                size = item.stat().st_size // 1024
                if size > 1024:
                    size = f"{size // 1024} MB"
                else:
                    size = f"{size} KB"
                print(f"   - {item.name} ({size})")
            elif item.is_dir():
                print(f"   - {item.name}/ (folder)")
    
    print(f"\n✅ Launcher: {target_exe}")
    print(f"✅ Main App: {main_exe}")
    
    if target_exe.exists() and main_exe.exists():
        print("\n🚀 To run:")
        print(f"   cd {target_dir}")
        print(f"   {LAUNCHER_NAME}.exe")
    
    print("=" * 60)

def main():
    """Main build process."""
    try:
        # Get version from user
        version = get_version_input()
        
        # Update version in files
        update_version_in_files(version)
        
        if build_launcher(version):
            # Find target directory again
            target_dir = find_zay_pos_exe() or os.getcwd()
            print_summary(target_dir, version)
        else:
            print("\n❌ Build failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
