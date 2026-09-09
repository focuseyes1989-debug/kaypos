# KAY Touch Local Print Bridge

Run the bridge on each Windows cashier PC connected to the receipt printer.
It reads that PC's installed printers and sends print/drawer jobs to its Windows
print queue. The server PC's printer settings are not used by Touch anymore.

## One-time setup

1. Update/restart the POS server and refresh Touch.
2. On the cashier PC, run `KAY_Touch_Print_Bridge.exe`. A standalone build is in
   `Output/TouchPrintBridge/`. Alternatively, install `requirements-pos-lite.txt`
   and run `Start_Touch_Print_Bridge.cmd` from this checkout.
3. Enter the Touch website address (for example `https://192.168.110.112:8000`),
   then click **Start local bridge**. Copy its pairing key.
4. In Touch, open **Settings → Printer → Local bridge setup**, paste the key,
   and click **Refresh Printers**. Select the local printer.
5. Choose paper under **Paper and advanced settings**, select auto print/drawer
   as wanted, then **Save Local Printer**. These preferences and the pairing key
   stay in this browser's local storage, not in the shared POS database.
6. Keep the bridge running/minimized. Launch it again after restarting Windows;
   it remembers its website and starts listening automatically.

Use the installed roll width (58mm/80mm) for GA-E200, and A4 for Canon G2100.
Bluetooth works only when that printer variant supports it and Windows exposes
it as an installed printer. Connect the cash drawer to the thermal printer's
cash-drawer port; an A4 inkjet cannot send a thermal drawer pulse successfully.

**Print Receipt** sends directly to the saved local printer. **Browser Print**
remains a manual fallback. Automatic actions run only after a sale is saved,
not when an old receipt is opened or New Sale is clicked. Defaults are off.

## Browser connection

The bridge listens only on `127.0.0.1:17861`. Allow the Touch site's local network
permission if the browser asks. Use a valid HTTPS Touch site; an untrusted
certificate/insecure page can prevent browser local-network access. Do not
turn off browser security checks. A blocked connection leaves the sale saved
and reports an error; Browser Print remains available.

The bridge accepts only its configured origin plus its random pairing key.
Do not share the key. Closing the bridge stops access. To pair a different site,
close the bridge and edit/delete `%LOCALAPPDATA%\KAY POS\Touch Print Bridge\bridge.json`
then restart and configure it again. Clearing browser data requires re-pairing.

Print submission means Windows accepted the job; it does not prove that paper
came out. If a request times out, check the Windows queue before a manual retry.
The local job ledger prevents automatic replay of the same sale's action,
including after restart; manual Print Receipt creates an intentional new job.

## Build and checks

Build on Windows with Python, PyQt6 and PyInstaller installed:

```
py -3 -m PyInstaller --noconfirm --distpath Output/TouchPrintBridge --workpath tmp/bridge-build KAY_Touch_Print_Bridge.spec
```

No-printer smoke check (writes JSON without printing/opening the drawer):

```
KAY_Touch_Print_Bridge.exe --check check-result.json
```

Tests:

```
py -3 -m unittest discover -s tests -p test_local_print_bridge.py
node tests/test_touch_local_printer.cjs
node tests/test_touch_sale_completion.cjs
node tests/test_touch_receipt_print.cjs
```
