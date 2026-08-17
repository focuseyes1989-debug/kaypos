"""Structured, side-effect-free diagnostics for pasted application errors."""

import re


class AIErrorDiagnostics:
    ERROR_MARKERS=("traceback","exception","error","failed","does not exist","cannot be matched","nonetype","access denied","not configured","no active","not working","connection refused","timed out","locked","unique constraint","duplicate key")

    @classmethod
    def handle(cls,text):
        if not cls.handles(text):return None
        diagnostic=cls.diagnose(text)
        return {"type":"diagnostic","data":[],"message":cls.format(diagnostic),"sql":"","diagnostic":diagnostic}

    @classmethod
    def handles(cls,text):
        value=(text or "").lower()
        return any(marker in value for marker in cls.ERROR_MARKERS)

    @classmethod
    def diagnose(cls,text):
        value=(text or "").lower();signature=re.sub(r"\s+"," ",cls.redact(text)).replace("`","'")[:500]
        if "coalesce" in value and ("cannot be matched" in value or "types text and timestamp" in value):
            return cls._item("Database type mismatch in COALESCE","High","PostgreSQL requires every COALESCE argument to resolve to a compatible type.",
                ["A date column is stored as TEXT while another value is TIMESTAMP.","A query written for mixed SQLite/PostgreSQL types lacks explicit casts."],
                ["Identify every expression inside COALESCE.","Check the database types of due_date, sale_date and created_at.","Confirm whether the application expects a date or timestamp result."],
                ["Cast text dates explicitly, for example NULLIF(due_date, '')::timestamp.","Alternatively cast every argument to DATE when time is not required.","Retest outstanding invoices and credit payment recording."],"Read-only query failure; existing records are normally unchanged.","Retry after the query uses one consistent date/time type.",signature)
        if "function datetime" in value and "does not exist" in value:
            return cls._item("SQLite datetime() used on PostgreSQL","High","PostgreSQL does not provide SQLite's datetime('now') function.",
                ["A SQLite-specific SQL fragment is running on PostgreSQL.","The database compatibility layer did not select the PostgreSQL expression."],
                ["Locate datetime('now') in the failing INSERT/UPDATE.","Confirm the active backend is PostgreSQL.","Check whether the date parameter is NULL and triggers the fallback."],
                ["Use CURRENT_TIMESTAMP or NOW() on PostgreSQL.","Use an explicit timestamp cast for supplied text values.","Keep SQLite and PostgreSQL expressions behind the compatibility helper."],"The failed transaction should be rolled back; verify that no partial payment was created.","Retry once, then verify payment and invoice balance records.",signature)
        if "no active zkteco device" in value or ("zkteco" in value and "not configured" in value):
            return cls._item("No active ZKTeco device configuration","Medium","Attendance sync could not find an enabled device record.",
                ["The device row has not been saved.","Status is Inactive.","The application is connected to a different database than Settings."],
                ["Open Settings > ZKTeco Devices.","Verify Device ID, IP, Port and Comm Key.","Confirm Status is Active and save.","Make sure the PC and device are on the reachable network."],
                ["Activate the correct device configuration.","Test the device connection before syncing.","Verify User ID to Employee ID mappings."],"No attendance data is deleted; the sync simply does not start.","Retry Sync K20 after the active device appears in Settings.",signature)
        if "int() argument" in value and "nonetype" in value:
            return cls._item("Missing numeric value converted with int()","Medium","A required numeric field returned NULL/None and was converted without validation.",
                ["A new record has no generated ID.","A combo box has no selected value.","A nullable database field is passed directly to int()."],
                ["Note which Save action produced the dialog.","Check required Device, Employee, Shift or User selections.","Inspect the log immediately above this error for the missing field."],
                ["Validate required selections before saving.","Use a safe default only when zero is valid.","For inserted rows, retrieve the generated ID explicitly on PostgreSQL."],"The save usually fails and rolls back; confirm whether a duplicate or partial record exists before retrying.","Fill every required selection and retry once.",signature)
        if "access denied" in value or "don't have permission" in value or "permission denied" in value:
            return cls._item("Role or session permission denied","Medium","The logged-in account does not currently have the permission key required by the page or action.",
                ["The role lacks the page permission.","Role permissions changed after login and the session is stale.","The user is linked to an unexpected role."],
                ["Check Settings > Roles & Permissions.","Confirm the user's assigned role.","Check both page View permission and action Manage permission.","Logout/login or restart after permission changes."],
                ["Grant only the required permission to the correct role.","Do not bypass the permission check in code.","Retest using the affected account."],"No business data is changed by an access-denied response.","Retry after refreshing the authenticated session.",signature)
        if "connection refused" in value or "timed out" in value or "timeout" in value:
            return cls._item("Network connection failed","Medium","The target service or device did not accept a connection within the allowed time.",
                ["Wrong IP/port.","Device or database service is offline.","Firewall, VLAN or routing blocks the connection."],
                ["Verify the configured host and port.","Test reachability from the POS computer.","Confirm the service/device is powered on.","Check firewall rules without disabling security globally."],
                ["Correct the endpoint or network route.","Restart only the affected service/device if authorized.","Increase timeout only after connectivity is proven."],"The requested operation normally fails before writing; verify transaction status before retrying.","Retry once after connectivity is restored.",signature)
        if "unique constraint" in value or "duplicate key" in value:
            return cls._item("Duplicate value violates a unique rule","Medium","A value that must be unique already exists.",
                ["Duplicate Employee ID, SKU, barcode, username or monthly payroll.","The same request was submitted twice."],
                ["Read the constraint/column name in the error.","Search existing records for the submitted value.","Check whether the first attempt actually succeeded."],
                ["Edit the existing record or use a genuinely unique value.","Do not delete history solely to bypass the constraint."],"The duplicate insert should roll back; the existing record remains.","Retry only after changing or selecting the existing record.",signature)
        if "database is locked" in value or "database locked" in value:
            return cls._item("Database write lock","Medium","Another transaction or application instance is holding the database write lock.",
                ["Multiple local POS instances are writing simultaneously.","A previous operation left a long transaction open."],
                ["Close duplicate POS windows safely.","Wait briefly for the current transaction to finish.","Check logs for an earlier unclosed transaction."],
                ["Retry after the writer completes.","Restart the application only if the lock remains and no transaction is active."],"Do not delete database lock/journal files manually; doing so can corrupt data.","Retry after confirming other writes have finished.",signature)
        return cls._item("Unclassified application error","Info","The message is recognized as an error, but it does not match a known safe diagnostic yet.",
            ["Invalid input, unavailable service, incompatible database query or an unhandled application state."],
            ["Record the page, action and exact time.","Check the application log around the same timestamp.","Confirm whether the action created or changed a record."],
            ["Restart only after saving current work.","Reproduce once with the same inputs.","Provide the redacted error and preceding log lines for code-level diagnosis."],"Unknown—verify the target record before repeating any payment, refund, payroll or stock action.","Avoid repeated submissions until you know whether the first operation committed.",signature)

    @staticmethod
    def _item(title,severity,meaning,causes,checks,fixes,risk,retry,signature):
        return {"title":title,"severity":severity,"meaning":meaning,"causes":causes,"checks":checks,"fixes":fixes,"risk":risk,"retry":retry,"signature":signature}

    @staticmethod
    def redact(text):
        value=str(text or "")
        value=re.sub(r"(?i)(postgres(?:ql)?://[^:\s/@]+:)[^@\s/]+@",r"\1[REDACTED]@",value)
        value=re.sub(r"(?i)\b(password|passwd|pwd|token|api[_ -]?key|secret|comm[_ -]?key)\b\s*[:=]\s*([^\s,;]+)",r"\1=[REDACTED]",value)
        return value

    @staticmethod
    def format(item):
        bullets=lambda values:"\n".join(f"• {value}" for value in values)
        steps=lambda values:"\n".join(f"{index}. {value}" for index,value in enumerate(values,1))
        return (f"🛠️ **{item['title']}**\n\n**Severity:** {item['severity']}\n\n**အဓိပ္ပာယ်**\n{item['meaning']}\n\n"
                f"**ဖြစ်နိုင်သောအကြောင်းရင်းများ**\n{bullets(item['causes'])}\n\n**စစ်ဆေးရန်**\n{steps(item['checks'])}\n\n"
                f"**ဖြေရှင်းရန်**\n{steps(item['fixes'])}\n\n**Data risk**\n{item['risk']}\n\n**Retry guidance**\n{item['retry']}\n\n"
                f"**Redacted signature**\n`{item['signature']}`")
