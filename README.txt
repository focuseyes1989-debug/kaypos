ZAY POS SYSTEM
==============

Quick Setup
-----------
1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Install dependencies:
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
4. Run the app:
   python main.py

Build
-----
Build the main POS executable:
   python build.py

Alternative build script:
   python build_exe.py

Build the launcher:
   python build_launcher.py

Important Runtime Folders
-------------------------
- database/pos.db is the local SQLite database.
- database/product_images/ stores product images.
- database/logos/ stores shop logos.
- database/backups/ stores local backups.
- logs/ stores runtime logs.

Common Issues
-------------
ERROR: No module named 'pkg_resources'
Solution:
   python -m pip uninstall barcode
   python -m pip install --upgrade --force-reinstall python-barcode

ERROR: Missing Excel export dependency
Solution:
   python -m pip install openpyxl

ERROR: Missing barcode dependency
Solution:
   python -m pip install python-barcode

ERROR: Database error
Solution:
1. Close the app.
2. Back up the database folder if it contains real shop data.
3. Restart the application.
4. Restore from a known-good backup if the database is corrupted.

ERROR: Permission denied
Solution:
1. Close the application.
2. Check that the database and backup folders are writable.
3. On Windows, run the application as Administrator only if needed.

Developer Notes
---------------
- Run a syntax check before packaging:
  python -m compileall -q ui models utils scripts main.py build.py build_exe.py launcher.py
- Run smoke tests:
  python -m unittest discover -s tests
- Run dependency consistency check:
  python -m pip check
- Do not commit runtime logs, local databases, WAL/SHM files, temp files, or generated build output.
