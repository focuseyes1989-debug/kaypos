# KAY Service Job Client

Standalone client application for staff workstations. It contains no POS or checkout features.

## Run from source

On Windows, double-click `service_job_client_main.pyw` to start the client without a Command Prompt window.

For troubleshooting with console output, run:

```powershell
python service_job_client_main.py
```

Enter the POS Server HTTPS address and a valid KAY POS username/password. The app refreshes every five seconds, displays new-job Windows notifications, and records the signed-in username when a job is completed.

Select a pending job and click **Start Job** to record your signed-in username and the server's start time. Every client shows **Working By**, **Started At**, and a blue **In Progress** status; the In Progress filter shows active jobs. Concurrent start requests allow only one worker to claim the job.

Click **Complete Job** when the work is finished. The job moves to the purple **Ready for Pickup** filter and records **Work Completed By / At**, retaining the original worker and start time. It has not yet been collected by the customer.

When the customer arrives, select the job under **Ready for Pickup** and click **Mark as Collected**. The confirmation displays the job's notes so staff can review payment/deposit notes. Confirming changes the status to green **Delivered** and separately records **Delivered By / At** using the signed-in staff account and server time. Payment information remains manually recorded in Notes; collection does not change it or infer payment status. Only ready jobs can be collected, and duplicate collection requests are rejected.

Older `completed` and `ready` jobs appear under **Ready for Pickup** and can be marked as collected without changing their existing work-completion records. Pending excludes jobs awaiting pickup; use the separate filters or All to see them.

The **Service Jobs** page in POS Lite uses the same Start Job, Complete Job, and Mark as Collected workflow, status colors, filters, and staff/time columns. While the page is open, it refreshes changed jobs from other workstations every five seconds and keeps the selected job when it remains in the filter. Appointment urgency is highlighted in the Appointment column. Notes can still be edited while a job awaits pickup, including older completed jobs.

Update and restart the POS Server as well as the clients for this feature (rebuild packaged executables). The server adds the tracking database columns automatically. Older records show a dash where no worker, time, or collection staff was recorded; historical collection is not inferred.

## Build the Windows app

```powershell
python build_service_job_client.py
```

The executable is created at `dist/KAY_Service_Job_Client/KAY_Service_Job_Client.exe`.
