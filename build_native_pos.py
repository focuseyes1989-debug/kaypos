"""Build and verify the separate KAY POS Native Windows distribution."""
import json
import os
from pathlib import Path
import subprocess
import sys


def source_state(root):
    try:
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True,timeout=10).stdout.strip()
        dirty=bool(subprocess.run(['git','status','--porcelain'],cwd=root,capture_output=True,text=True,check=True,timeout=10).stdout.strip())
        return revision,dirty
    except (OSError,subprocess.SubprocessError):return 'unknown',True


def build_arguments(root):
    import PyQt6
    qt_bin = Path(PyQt6.__file__).resolve().parent / 'Qt6' / 'bin' / '*.dll'
    return [str(root/'kay_pos_native.py'),'--name','KAY_POS_Native','--specpath',str(root/'build'/'native_spec'),
        '--distpath',str(root/'dist'),'--workpath',str(root/'build'/'native'),'--noconfirm','--clean','--windowed','--onedir',
        '--icon',str(root/'assets'/'kay'/'kay_multi.ico'),'--version-file',str(root/'native_version.txt'),
        '--add-data',f'{root / "assets" / "kay" / "kay_multi.ico"};assets/kay','--add-data',f'{root / "native_version.json"};.',
        '--add-binary',f'{qt_bin};.',
        '--collect-submodules','native_pos','--hidden-import','psycopg']


def verify_and_smoke(root):
    from native_pos.release import distribution_manifest
    directory=root/'dist'/'KAY_POS_Native';revision,dirty=source_state(root)
    result=distribution_manifest(directory,revision,dirty)
    environment=os.environ.copy();environment['QT_QPA_PLATFORM']='offscreen'
    completed=subprocess.run([str(directory/'KAY_POS_Native.exe'),'--smoke-test'],cwd=directory,env=environment,timeout=45)
    if completed.returncode:raise RuntimeError(f'Packaged Native smoke test failed with exit code {completed.returncode}')
    result['smoke_test']='passed'
    target=directory/'build-manifest.json';temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(target)
    return result


def main():
    root=Path(__file__).resolve().parent
    import PyInstaller.__main__
    PyInstaller.__main__.run(build_arguments(root))
    result=verify_and_smoke(root)
    print(f"Built {result['product']} {result['version']} · smoke test passed · SHA-256 {result['executable_sha256']}")


if __name__=='__main__':main()
