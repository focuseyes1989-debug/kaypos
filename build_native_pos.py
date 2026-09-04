"""Build the Native preview into its own output directory; no legacy artifacts removed."""
from pathlib import Path
import PyInstaller.__main__

def main():
    root=Path(__file__).resolve().parent
    PyInstaller.__main__.run([
        str(root/'kay_pos_native.py'), '--name', 'KAY_POS_Native',
        '--specpath',str(root/'build'/'native_spec'),
        '--distpath',str(root/'dist'), '--workpath',str(root/'build'/'native'),
        '--noconfirm','--windowed','--onedir',
        '--icon',str(root/'assets'/'kay'/'kay_multi.ico'),
        '--add-data',f'{root / "assets" / "kay" / "kay_multi.ico"};assets/kay',
        '--collect-submodules','native_pos','--hidden-import','psycopg',
    ])

if __name__=='__main__':
    main()
