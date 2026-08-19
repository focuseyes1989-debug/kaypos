# KAY Car Management Client

Phase 5 provides a standalone PyQt6 Windows client with persistent LAN server
settings, validated data entry, searchable/paginated records, record details,
editing, deletion confirmation, and duplicate warnings before save/update.

Connection, record loading, and save workflows display non-blocking activity
indicators and contextual retry controls. Safe read-only requests retry one
dropped connection automatically. Save, update, and delete requests are never
automatically retried because the server may already have committed the change.

The input page supports two workflows:

- **New Car and Driver**: enter all vehicle and driver fields.
- **Existing Car · New Driver**: choose a unique existing car; vehicle, engine,
  and frame details are filled and locked, while only the new driver's details
  need to be entered. After saving, the selected car remains ready for another
  driver entry.

A duplicate warning is shown only when both Car Number and driver NRC match an
existing record. Reusing the same car, engine, or frame for a different driver
is supported and does not trigger a warning.

Run it from the project folder:

```powershell
python car_client_main.py
```

Enter the KAY POS server PC's LAN IP address. The default Car Management TCP
port is `12345`. Start KAY POS Server Manager before testing the connection and
allow inbound TCP port `12345` through Windows Firewall on the server PC.

The client stores only host, port, and timeout settings in the current Windows
user profile. It does not contain or store PostgreSQL credentials.

## Auto-filled car forms

On **Car Records**, select a database row and click **Auto Fill Forms**. The
preview dialog overlays that record on the four original templates in
`assets/car_images/1.jpg` through `4.jpg`. Use the page selector to inspect each
page and the zoom selector for fit-width or percentage viewing.

- **Save Page Image** saves the currently displayed completed form as an image.
- **Export 4-Page PDF** creates one print-ready PDF containing all four forms.
- The original JPG templates are opened read-only and are never modified.
- Windows 10/11's built-in **Myanmar Text** font is preferred for completed
  forms. Bundled Noto Sans Myanmar remains the fallback for environments where
  the Windows font is unavailable. Auto-filled values use bold weight for
  clearer printing and scanning.
- Long driver names on page 4 wrap inside the Driver Name table cell instead
  of overflowing into the Age column.

### Printing

Open **Print Settings** from the form preview to enter any required page order,
including repeated pages such as `1,1,2,3,4,2,3,2,3,4`. The client saves the
page sequence, selected Windows printer, copy count, color mode, and duplex mode
for the next app session. Printing uses A4 portrait pages and preserves each
form's aspect ratio inside the printer's printable area.

The sidebar **Print** page manages these defaults without opening a record.
**Printer Preferences** opens the Windows printer dialog and saves the standard
preferences exposed by Qt, including printer, paper size/orientation, resolution,
copies, color mode, and duplex mode. Driver-only options remain subject to the
installed Windows printer driver.
