# KAY Service Job Client

Standalone client application for staff workstations. It contains no POS or checkout features.

## Run from source

On Windows, double-click `service_job_client_main.pyw` to start the client without a Command Prompt window.

For troubleshooting with console output, run:

```powershell
python service_job_client_main.py
```

Enter the POS Server HTTPS address and a valid KAY POS username/password. The app refreshes every five seconds, displays new-job Windows notifications, and records the signed-in username when a job is completed.

## Build the Windows app

```powershell
python build_service_job_client.py
```

The executable is created at `dist/KAY_Service_Job_Client/KAY_Service_Job_Client.exe`.
