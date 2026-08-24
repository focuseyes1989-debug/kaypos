# KAY LAN/Wi-Fi Printer Server Deployment

## Server PC

1. Give the Server PC a static LAN address or DHCP reservation.
2. Generate three different long random keys and set `KAY_PRINTER_ADMIN_KEY`,
   `KAY_PRINTER_CLIENT_KEY`, and `KAY_PRINTER_ENROLLMENT_KEY` in `.env`.
3. Restart KAY POS Server Manager and start the POS HTTPS service.
4. Allow the configured POS server port (default TCP 8000) through Windows
   Firewall only for the Private network profile/local subnet.

## Build the Agent

Run `py build_printer_agent.py`. Deploy the resulting
`dist_printer_agent/KAY_Printer_Agent.exe` to each printer PC.

## Each Printer PC

1. Run `KAY_Printer_Agent.exe --configure`.
2. Enter the Server URL, for example `https://192.168.1.10:8000`.
3. Enter the one-time enrollment key.
4. Enable the self-signed certificate option when using Server Manager's local
   HTTPS certificate.
5. Enable Windows startup and click **Test, Enroll and Save**.
6. Start `KAY_Printer_Agent.exe`; it remains in the Windows system tray.

## Each POS PC

Open Print Settings, choose **LAN/Wi-Fi network printer**, enter the Server URL
and `KAY_PRINTER_CLIENT_KEY`, refresh, choose that PC's printer, and save.

## Recovery

- Server unavailable: jobs remain pending in PostgreSQL and Agents reconnect
  automatically every ten seconds.
- Agent stopped during printing: the job times out and can be retried in Server
  Manager.
- Token replacement: run the Agent with `--configure` and enter the enrollment
  key again, or use `--reset-enrollment --enrollment-key KEY` from a terminal.
- Windows startup removal: run `KAY_Printer_Agent.exe --remove-startup`.

