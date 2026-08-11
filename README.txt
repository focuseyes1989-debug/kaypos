ZAY POS
=======

ZAY POS သည် Windows ပေါ်တွင် အသုံးပြုရန်ရေးသားထားသော Python/PyQt6 POS
application ဖြစ်သည်။ Sales, Products, Inventory, Customers, Suppliers,
Reports, Receipts, Backup/Restore, Launcher Auto Update, Cashier mode နှင့်
AI/assistant pages စသည်တို့ ပါဝင်သည်။


Project Structure
-----------------
- main.py
  Main POS application entry point.

- cashier_main.py
  Cashier mode entry point.

- launcher.py
  Update စစ်ခြင်း၊ update package download/install လုပ်ခြင်း၊ Main/Cashier
  mode launch လုပ်ခြင်းတို့အတွက် launcher.

- app/
  Application bootstrap, startup helpers, config and launcher helpers.

- models/
  SQLite database schema, migrations, queries, recovery and maintenance code.

- ui/
  PyQt6 UI pages, dialogs, widgets and design system.

- services/
  Business/service layer helpers.

- utils/
  Paths, backup, permissions, receipts, currency, audio, Telegram and other
  utility modules.

- scripts/
  Update package generation, GitHub release upload and maintenance scripts.

- tests/
  Unit/smoke tests for selected features and release helpers.


Requirements
------------
- Windows 10/11
- Python 3.10 or newer
- Git
- Internet connection for GitHub auto update/upload features

Install dependencies:

   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt


Run From Source
---------------
Main POS:

   python main.py

Cashier mode:

   python cashier_main.py

Launcher:

   python launcher.py


Build EXE
---------
The main POS application is built as PyInstaller onedir output. Onedir is used
because startup and runtime behavior are more stable for this project, and it
keeps native modules such as SQLite DLL/PYD files available beside the app.

Build main POS:

   python build_exe.py

Build launcher:

   python build_launcher.py

Alternative full build script:

   python build.py

Expected output:

   dist/ZAY_POS_v<version>/ZAY_POS.exe
   dist/ZAY_POS_v<version>/ZAY_POS_Launcher.exe
   dist/ZAY_POS_v<version>/_internal/

Important: the launcher is built separately. The main POS is onedir, while the
launcher can be onefile so it does not overwrite the main app _internal folder.


Generate Update Package
-----------------------
After building the app, generate the update zip:

   python scripts/generate_update.py --version 1.5.9 --repo focuseyes1989-debug/ZAY_POS

Expected output:

   update_build/ZAY_POS_v1.5.9_update.zip
   update_build/version.json

The update zip must contain:

   ZAY_POS.exe
   ZAY_POS_Launcher.exe
   version.txt
   _internal/

If launcher update install shows:

   Installation failed: Update package does not contain ZAY_POS.exe

then the uploaded release asset is probably the wrong zip. Regenerate the update
zip from the full dist/ZAY_POS_v<version> folder and replace the GitHub release
asset with update_build/ZAY_POS_v<version>_update.zip.


Upload Update To GitHub Release
-------------------------------
Set a GitHub token first:

   $env:GITHUB_TOKEN="YOUR_TOKEN_HERE"

Upload the generated update zip:

   python scripts/upload_update.py --version 1.5.9 --zip update_build/ZAY_POS_v1.5.9_update.zip --repo focuseyes1989-debug/ZAY_POS

The token needs permission to create/edit releases and upload release assets.


Version Notes
-------------
When releasing a new version:

1. Build main POS with the new version.
2. Build launcher with the same version.
3. Generate update package with the same version.
4. Upload/replace the GitHub release asset.
5. Commit and push source changes to GitHub main branch.

Use x.y.z format, for example:

   1.5.9
   1.6.0
   2.0.0


Runtime Data
------------
The following files/folders are local runtime data and should not be committed:

- database/*.db
- database/product_images/
- database/images/
- database/logos/
- utils/database/
- logs/
- temp/
- build/
- dist/
- dist_launcher/
- update_build/
- _internal/
- *.zip

Local shop data, product images, logos, backups and logs should stay on the
user's computer only.


Database Troubleshooting
------------------------
If the app shows a database error, do not assume the database is corrupted first.
Check logs before restoring from backup.

Logs are usually stored in:

   logs/
   dist/ZAY_POS_v<version>/logs/

Common real causes:

- Missing _sqlite3 module in packaged EXE
- sqlite3.dll or _sqlite3.pyd missing from _internal/
- Migration error
- Permission denied in Program Files
- Disk full
- Real SQLite database corruption

If the log shows:

   No module named '_sqlite3'

then it is a build/package issue, not a corrupted database issue. Rebuild the
main POS as onedir and make sure _internal contains:

   _sqlite3.pyd
   sqlite3.dll


Developer Checks
----------------
Syntax check staged or changed Python files:

   python -m py_compile main.py launcher.py build.py build_exe.py build_launcher.py

Run tests if pytest is installed:

   python -m pytest tests

Dependency consistency check:

   python -m pip check


Browser Cashier Server - Phase 1
--------------------------------
The browser cashier mode lets one Server PC own the SQLite database while other
computers on the same router use Cashier mode from a web browser.

Install the server dependencies:

   python -m pip install -r requirements.txt

Start the server on the Server PC:

   python run_pos_server.py --host 0.0.0.0 --port 8000

Open Cashier mode from the Server PC:

   http://127.0.0.1:8000

Open Cashier mode from another computer on the same router:

   http://SERVER_PC_IP:8000

Example:

   http://192.168.1.10:8000

If other computers cannot open the page, allow TCP port 8000 in Windows
Firewall on the Server PC.

Important: do not share database/pos.db directly over the network. Browser
cashier clients must use the API server so only the Server PC writes to SQLite.

Client Cash Drawer Helper
-------------------------
To open the cash drawer connected to a client computer, run this helper on that
client PC:

   python run_client_cashdrawer_helper.py --printer "YOUR RECEIPT PRINTER NAME" --port 8765

Keep the helper window open while using Browser Cashier on that client. In the
Browser Cashier Sale Details panel, the Client helper URL should be:

   http://127.0.0.1:8765

The browser print dialog prints on the client computer. The cash drawer button
uses the local helper so the drawer attached to the client printer can open.


Git Workflow
------------
Before pushing:

   git status
   git add .
   git commit -m "Update ZAY POS source"
   git pull --rebase origin main
   git push origin main

If Git says index.lock already exists:

1. Make sure no other git command or commit editor is running.
2. If no git process is running, remove:

   .git/index.lock

3. Run the git command again.


Useful Commands
---------------
Check current branch:

   git status --short --branch

Check latest commits:

   git log --oneline --decorate -5

Check update zip content:

   python -m zipfile -l update_build/ZAY_POS_v1.5.9_update.zip


License / Ownership
-------------------
This project belongs to the ZAY POS project owner. Do not publish private shop
data, database files, product photos, logs, tokens or local configuration files.
