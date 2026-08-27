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

## Dashboard Phase 1

Dashboard is the default landing page. Its responsive foundation includes a
manual refresh action, asynchronous Car Management service/PostgreSQL health
check, loading feedback, contextual retry, and error handling. Summary card
slots are prepared for Phase 2 without calculating business totals yet.

## Dashboard Phase 2

Dashboard refresh now loads PostgreSQL records asynchronously and calculates
Total Records, Unique Cars, unique Drivers, Multiple-driver Cars, Added Today,
and Missing Information. Cars are normalized by Car Number; drivers use NRC as
their primary identity with normalized name/phone as a fallback. A record is
flagged incomplete when any important vehicle or driver detail is blank.

## Dashboard Phase 3

Recent Activity shows the latest 5, 10, or 20 timestamped records with car,
driver, vehicle, phone, and update time. Double-click a row or use **View
Record** for full details. Successful save, edit, and delete operations mark the
dashboard stale so it refreshes automatically when the user returns. The legacy
schema has one timestamp, so created and edited events cannot yet be separated.

## Dashboard Phase 4

Data Quality & Alerts provides clickable filters for missing age, phone,
address, engine, and frame values, plus possible duplicate car-driver records
and conflicting vehicle details. Alerts open a filtered table with full record
details on double-click. A shared car with different driver NRC values remains
valid and is not treated as a duplicate.

## Dashboard Phase 5

Charts & Insights adds dependency-free charts for monthly additions, car type,
car kind, most reused cars by distinct driver count, and complete versus
incomplete records. Filters include Today, This Week, This Month, This Year,
All Time, and a calendar-based Custom Range. The dashboard is scrollable so the
charts remain usable on smaller displays.

## Dashboard Phase 6

Quick Actions link directly to new-car entry, existing-car/new-driver entry,
record search, auto-filled forms, Print, and refresh. Dashboard Settings controls
summary-card visibility and requires at least one visible card. Card visibility,
recent-activity row count, chart period, and custom start/end dates persist in
the current Windows user profile across app restarts.

## Background Owner Web Print Agent

The Owner Web Print Agent continues running in the Windows system tray when
the Car Management window is closed. The Print page can enable launch after
Windows login and close-to-tray behavior. Double-click the tray icon to reopen
the app. Use **Exit Car Management and Print Agent** in the tray menu only when
the web printer should deliberately go offline.

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

While a print job is being prepared, the Print button and related controls are
disabled and a per-page progress bar is shown. Controls are enabled again only
after every requested page has been submitted, or safely restored after an error.
