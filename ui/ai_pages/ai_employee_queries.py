"""Permission-aware Employee Management queries for AI Chat."""

import re
import unicodedata
import calendar
from difflib import SequenceMatcher
from datetime import date, timedelta

from services import employee_service as service
from utils.permissions import PermissionManager
from ui.ai_pages.ai_query_handlers import QueryHandlers


class EmployeeQueryHandler:
    DOMAIN_WORDS = (
        "employee", "employees", "staff", "attendance", "check-in", "check in",
        "check-out", "check out", "shift", "payroll", "salary", "leave",
        "commission", "advance", "cash session", "performance",
        "phone number", "phone", "mobile", "contact number",
        "address", "position", "department", "branch", "hire date", "joined",
        "emergency contact", "national id", "zkteco user id", "profile",
        "ဝန်ထမ်း", "အလုပ်ဝင်", "အလုပ်ဆင်း", "တက်ရောက်", "အလုပ်ချိန်",
        "လစာ", "ခွင့်", "ကော်မရှင်", "ကြိုတင်လစာ", "စွမ်းဆောင်ရည်",
        "ဖုန်းနံပါတ်", "ဖုန်း", "ဆက်သွယ်ရန်နံပါတ်",
        "လိပ်စာ", "ရာထူး", "ဌာန", "ဆိုင်ခွဲ", "အလုပ်ဝင်ရက်",
        "အရေးပေါ်ဆက်သွယ်ရန်", "မှတ်ပုံတင်", "ကိုယ်ရေးအချက်အလက်",
    )
    NAME_STOP_WORDS = DOMAIN_WORDS + (
        "summary", "list", "detail", "details", "today", "yesterday", "tomorrow",
        "this month", "current month", "last month", "previous month", "month", "history", "balance", "remaining",
        "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
        "missing", "late", "before", "after", "approved", "pending", "rejected",
        "open", "closed", "outstanding", "paid", "unpaid", "draft", "for", "of", "to", "from",
        "show", "find", "search", "what", "when", "how", "is", "the",
        "page", "open", "go to", "show page", "view page",
        "phone number", "phone", "mobile", "contact number", "ph",
        "address", "position", "department", "branch", "hire date", "joined",
        "emergency contact", "national id", "zkteco user id", "profile",
        "ဒီနေ့", "ယနေ့", "မနေ့က", "စာရင်း", "အကျဉ်းချုပ်", "ရှာ", "ပြပါ",
        "ဒီလ", "ယခုလ", "ပြီးခဲ့တဲ့လ", "လွန်ခဲ့တဲ့လ", "သမိုင်း", "လက်ကျန်", "ကရော", "တဲ့",
        "ဘယ်သူ", "ဘယ်လောက်", "မရှိ", "ရှိ", "စောဝင်", "နောက်ကျ",
        "ဖွင့်", "ဖွင့်", "စာမျက်နှာ", "ပေး", "ပေးပါ",
        "ဖုန်းနံပါတ်", "ဖုန်း", "ဆက်သွယ်ရန်နံပါတ်", "မှ", "ရဲ့", "၏",
        "လိပ်စာ", "ရာထူး", "ဌာန", "ဆိုင်ခွဲ", "အလုပ်ဝင်ရက်",
        "အရေးပေါ်ဆက်သွယ်ရန်", "မှတ်ပုံတင်", "ကိုယ်ရေးအချက်အလက်",
    )

    @classmethod
    def handles(cls, query):
        text=(query or "").lower()
        contact_query=bool(re.search(r"(?:^|\s)ph(?:$|\s|[?.!,])",text))
        return any(word in text for word in cls.DOMAIN_WORDS) or contact_query or bool(re.search(r"\bEMP-\d+\b", query or "", re.I))

    @classmethod
    def handle(cls, query, user_id):
        if not cls.handles(query):return None
        permissions=cls._permissions(user_id);text=(query or "").lower()
        view=cls._view(text)
        required={
            "attendance":"attendance", "shifts":"shifts", "payroll":"payroll",
            "leave":"leave", "finance":"employee_finance",
            "performance":"employee_performance", "cash_sessions":"cash_sessions",
        }.get(view,"employees")
        if required not in permissions:
            return cls._result("🔒 You don't have permission to view this Employee Management information.")
        try:
            return getattr(cls,f"_{view}")(query,text,permissions)
        except Exception as exc:
            return cls._result(f"❌ Employee query failed: {exc}")

    @staticmethod
    def _permissions(user_id):
        try:return PermissionManager.get_user_permissions(int(user_id))
        except (TypeError,ValueError):return set()

    @staticmethod
    def _view(text):
        if any(x in text for x in ("cash session","cash-session","ငွေစာရင်း")):return "cash_sessions"
        if any(x in text for x in ("performance","sales performance","စွမ်းဆောင်ရည်")):return "performance"
        if any(x in text for x in ("commission","advance","ကော်မရှင်","ကြိုတင်လစာ")):return "finance"
        if any(x in text for x in ("payroll","salary","လစာ")):return "payroll"
        if any(x in text for x in ("leave","ခွင့်")):return "leave"
        if any(x in text for x in ("shift","အလုပ်ချိန်")):return "shifts"
        if any(x in text for x in ("attendance","check-in","check in","check-out","check out","late","အလုပ်ဝင်","အလုပ်ဆင်း","တက်ရောက်","နောက်ကျ")):return "attendance"
        return "employees"

    @staticmethod
    def _result(message,data=None):return {"type":"employee_query","data":data or [],"message":message,"sql":""}

    @staticmethod
    def _date(query):
        parsed,_label=QueryHandlers.parse_date_expression(query)
        return parsed or date.today().isoformat()

    @classmethod
    def _date_range(cls,query):
        text=(query or "").lower();today=date.today()
        explicit=re.findall(r"\b(20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b",text)
        if len(explicit)>=2:return min(explicit[0],explicit[1]),max(explicit[0],explicit[1])
        month_match=re.search(r"\b(20\d{2})-(0[1-9]|1[0-2])\b",text)
        if month_match:return cls._month_range(*map(int,month_match.groups()))
        months={name.lower():number for number,name in enumerate(calendar.month_name) if name}
        months.update({name.lower():number for number,name in enumerate(calendar.month_abbr) if name})
        for name,number in sorted(months.items(),key=lambda item:len(item[0]),reverse=True):
            if re.search(rf"\b{re.escape(name)}\b",text):
                year=re.search(r"\b(20\d{2})\b",text)
                return cls._month_range(int(year.group(1)) if year else today.year,number)
        if any(word in text for word in ("this month","current month","ဒီလ","ယခုလ")):
            return cls._month_range(today.year,today.month)
        if any(word in text for word in ("last month","previous month","ပြီးခဲ့တဲ့လ","လွန်ခဲ့တဲ့လ")):
            previous=today.replace(day=1)-timedelta(days=1)
            return cls._month_range(previous.year,previous.month)
        if explicit:return explicit[0],explicit[0]
        day=cls._date(query);return day,day

    @staticmethod
    def _month_range(year,month):
        return f"{year:04d}-{month:02d}-01",f"{year:04d}-{month:02d}-{calendar.monthrange(year,month)[1]:02d}"

    @staticmethod
    def _normalize(value):
        value=unicodedata.normalize("NFKC",str(value or "")).casefold()
        return " ".join(re.sub(r"[^\w\u1000-\u109f]+"," ",value).split())

    @classmethod
    def _employee_search_term(cls,query):
        text=cls._normalize(query)
        text=re.sub(r"\bemp\s*\d+\b|\b20\d{2}[ -]\d{1,2}(?:[ -]\d{1,2})?\b|\b\d{1,2}[ ./-]\d{1,2}[ ./-]\d{4}\b|\b20\d{2}\b"," ",text,flags=re.I)
        for word in sorted(cls.NAME_STOP_WORDS,key=len,reverse=True):
            text=text.replace(cls._normalize(word)," ")
        return " ".join(text.split())

    @classmethod
    def _employee_match(cls,rows,query):
        match=re.search(r"\bEMP-\d+\b",query or "",re.I)
        if match:
            number=match.group(0).upper();return [x for x in rows if str(x.get("employee_no") or "").upper()==number]
        normalized_query=cls._normalize(query)
        full_matches=[x for x in rows if cls._normalize(x.get("full_name")) and cls._normalize(x.get("full_name")) in normalized_query]
        if full_matches:return full_matches
        term=cls._employee_search_term(query)
        if not term:return rows
        substring=[x for x in rows if term in cls._normalize(x.get("full_name"))]
        if substring:return substring
        tokens=[token for token in term.split() if len(token)>=2]
        token_matches=[x for x in rows if tokens and all(token in cls._normalize(x.get("full_name")) for token in tokens)]
        if token_matches:return token_matches
        scored=[(SequenceMatcher(None,term,cls._normalize(x.get("full_name"))).ratio(),x) for x in rows]
        best=max((score for score,_row in scored),default=0)
        return [row for score,row in scored if best>=0.58 and score>=best-0.04]

    @classmethod
    def _employees(cls,query,text,permissions=None):
        rows=service.list_employees();matched=cls._employee_match(rows,query)
        asks_phone=(
            any(x in text for x in ("phone number","phone","mobile","contact number","ဖုန်းနံပါတ်","ဖုန်း","ဆက်သွယ်ရန်နံပါတ်"))
            or bool(re.search(r"(?:^|\s)ph(?:$|\s|[?.!,])",text))
        )
        asks_list=any(x in text for x in ("list","who","ဘယ်သူ","စာရင်း")) or matched is not rows
        term=cls._employee_search_term(query)
        if term and not matched:return cls._result(f"🔍 No employee matched '{term}'. Try a fuller name or an Employee ID such as EMP-0008.")
        if asks_phone:
            if not matched:
                return cls._result("🔍 No matching employee was found. Try a fuller name or an Employee ID such as EMP-0008.")
            if len(matched)>1:
                choices="\n".join(f"• {x['employee_no']} — {x['full_name']}" for x in matched[:10])
                return cls._result(
                    "🔎 **More than one employee matched.** Please ask again with the Employee ID or fuller name:\n\n"+choices,
                    matched,
                )
            employee=matched[0]
            phone=str(employee.get("phone") or "").strip()
            value=phone if phone else "Not recorded"
            return cls._result(
                f"📞 **{employee['full_name']} — Phone Number**\n\n"
                f"• Employee ID: {employee['employee_no']}\n"
                f"• Phone: {value}",
                matched,
            )
        requested=cls._requested_profile_fields(text)
        if requested and matched is not rows:
            if len(matched)>1:
                choices="\n".join(f"• {x['employee_no']} — {x['full_name']}" for x in matched[:10])
                return cls._result("🔎 **More than one employee matched.** Use the Employee ID or fuller name:\n\n"+choices,matched)
            employee=matched[0]
            if {"national_id","emergency_contact","notes"}.intersection(requested) and "manage_employees" not in (permissions or set()):
                return cls._result("🔒 Emergency contact, National ID and private employee notes require Manage Employees permission.")
            values={
                "address":("Address",employee.get("address")), "position":("Position",employee.get("position")),
                "department":("Department",employee.get("department")), "branch":("Branch",employee.get("branch")),
                "hire_date":("Hire Date",employee.get("hire_date")), "status":("Status",employee.get("employment_status")),
                "zkteco_user_id":("ZKTeco User ID",employee.get("zkteco_user_id")),
                "national_id":("National ID",employee.get("national_id")), "notes":("Notes",employee.get("notes")),
                "emergency_contact":("Emergency Contact"," — ".join(str(x) for x in (employee.get("emergency_contact_name"),employee.get("emergency_contact_phone")) if x)),
            }
            lines=[f"• {values[key][0]}: {values[key][1] or 'Not recorded'}" for key in requested if key in values]
            return cls._result(f"👤 **{employee['full_name']} — Employee Profile**\n\n• Employee ID: {employee['employee_no']}\n"+"\n".join(lines),matched)
        counts={status:sum(str(x.get("employment_status"))==status for x in rows) for status in ("Active","On Leave","Resigned")}
        message=("👥 **Employee Summary**\n\n"
                 f"• Total: {len(rows)}\n• Active: {counts['Active']}\n"
                 f"• On Leave: {counts['On Leave']}\n• Resigned: {counts['Resigned']}")
        if asks_list:
            message+="\n\n**Employees:**\n"+"\n".join(
                f"• {x['employee_no']} — {x['full_name']} ({x.get('position') or 'No position'}, {x.get('employment_status')})"
                for x in matched[:20])
            if len(matched)>20:message+=f"\n• ... and {len(matched)-20} more"
        return cls._result(message,matched)

    @staticmethod
    def _requested_profile_fields(text):
        mappings=(
            ("address",("address","လိပ်စာ")), ("position",("position","ရာထူး")),
            ("department",("department","ဌာန")), ("branch",("branch","ဆိုင်ခွဲ")),
            ("hire_date",("hire date","joined","အလုပ်ဝင်ရက်")),
            ("status",("employment status","employee status","အလုပ်အခြေအနေ")),
            ("zkteco_user_id",("zkteco user id","device user id","စက် user id")),
            ("national_id",("national id","မှတ်ပုံတင်")),
            ("emergency_contact",("emergency contact","အရေးပေါ်ဆက်သွယ်ရန်")),
            ("notes",("private notes","employee notes","မှတ်ချက်")),
        )
        requested=[key for key,words in mappings if any(word in text for word in words)]
        if any(word in text for word in ("profile","details","detail","ကိုယ်ရေးအချက်အလက်")):
            requested=["address","position","department","branch","hire_date","status","zkteco_user_id"]
        return requested

    @classmethod
    def _attendance(cls,query,text,permissions=None):
        start,end=cls._date_range(query);rows=cls._employee_match(service.list_attendance(start,end),query)
        title="Attendance"
        if any(x in text for x in ("missing check-in","missing check in","no check-in","check-in မရှိ","အလုပ်ဝင် မရှိ")):
            rows=[x for x in rows if not x.get("check_in")];title="Missing Check-in"
        elif any(x in text for x in ("missing check-out","missing check out","no check-out","check-out မရှိ","အလုပ်ဆင်း မရှိ")):
            rows=[x for x in rows if not x.get("check_out")];title="Missing Check-out"
        elif any(x in text for x in ("before shift","စောဝင်")):
            rows=[x for x in rows if x.get("check_in") and x.get("shift_start") and str(x["check_in"])[:5]<str(x["shift_start"])[:5]];title="Check-in Before Shift"
        elif any(x in text for x in ("late","after shift","နောက်ကျ")):
            rows=[x for x in rows if x.get("status")=="Late" or (x.get("check_in") and x.get("shift_start") and str(x["check_in"])[:5]>str(x["shift_start"])[:5])];title="Late / After Shift"
        counts={status:sum(str(x.get("status") or "").lower()==status.lower() for x in rows) for status in ("Present","Late","Incomplete","Absent","Half-day","Leave")}
        late_minutes=sum(int(x.get("late_minutes") or 0) for x in rows)
        period=start if start==end else f"{start} to {end}"
        message=(f"🕒 **{title} — {period}**\n\nTotal records: {len(rows)}\n"
                 f"Present: {counts['Present']} | Late: {counts['Late']} | Incomplete: {counts['Incomplete']}\n"
                 f"Absent: {counts['Absent']} | Half-day: {counts['Half-day']} | Leave: {counts['Leave']}\n"
                 f"Total late minutes: {late_minutes}")
        if rows:message+="\n\n"+"\n".join(f"• {x.get('attendance_date')} — {x['employee_no']} — {x['full_name']}: {x.get('check_in') or '—'} / {x.get('check_out') or '—'} ({x.get('status')})" for x in rows[:30])
        if len(rows)>30:message+=f"\n• ... and {len(rows)-30} more records"
        return cls._result(message,rows)

    @classmethod
    def _shifts(cls,query,text,permissions=None):
        rows=cls._employee_match(service.list_employee_shift_assignments(),query)
        message=f"🗓️ **Employee Shift Assignments**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['shift_name']} ({x['start_time']}–{x['end_time']}), from {x['effective_from']}" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _leave(cls,query,text,permissions=None):
        status="Pending" if any(x in text for x in ("pending","စောင့်")) else "Approved" if any(x in text for x in ("approved","အတည်ပြု")) else "Rejected" if "rejected" in text else "All"
        rows=cls._employee_match(service.list_leave(status),query)
        totals={value:sum(float(x.get("days") or 0) for x in rows if x.get("status")==value) for value in ("Approved","Pending","Rejected")}
        message=(f"🏖️ **{status} Leave History**\n\nRecords: {len(rows)}\n"
                 f"Approved days: {totals['Approved']:g} | Pending days: {totals['Pending']:g} | Rejected days: {totals['Rejected']:g}")
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['leave_type']} ({x['start_date']} to {x['end_date']}) — {x['status']}" for x in rows[:20])
        if any(x in text for x in ("balance","remaining","လက်ကျန်")):
            message+="\n\nℹ️ Leave entitlement is not configured, so an exact remaining balance cannot be calculated. The values above are recorded history."
        return cls._result(message,rows)

    @classmethod
    def _payroll(cls,query,text,permissions=None):
        match=re.search(r"\b(20\d{2}-(?:0[1-9]|1[0-2]))\b",query or "")
        period=match.group(1) if match else cls._date_range(query)[0][:7]
        rows=cls._employee_match(service.list_payrolls(period),query)
        if "paid" in text:rows=[x for x in rows if x.get("status")=="Paid"]
        elif any(x in text for x in ("draft","unpaid","မပေး")):rows=[x for x in rows if x.get("status")=="Draft"]
        total=sum(float(x.get("net_salary") or 0) for x in rows)
        message=f"💵 **Payroll — {period}**\n\nRecords: {len(rows)}\nNet Total: {total:,.0f} Ks"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {float(x.get('net_salary') or 0):,.0f} Ks ({x['status']})" for x in rows[:20])
        if len(rows)==1:
            x=rows[0]
            message+=("\n\n**Breakdown**\n"
                      f"• Basic salary: {float(x.get('basic_salary') or 0):,.0f} Ks\n"
                      f"• Allowance: {float(x.get('allowance') or 0):,.0f} Ks\n"
                      f"• Overtime: {float(x.get('overtime_amount') or 0):,.0f} Ks\n"
                      f"• Bonus: {float(x.get('bonus') or 0):,.0f} Ks\n"
                      f"• Late deduction: {float(x.get('late_deduction') or 0):,.0f} Ks\n"
                      f"• Absence deduction: {float(x.get('absence_deduction') or 0):,.0f} Ks\n"
                      f"• Advance deduction: {float(x.get('advance_deduction') or 0):,.0f} Ks\n"
                      f"• Other deduction: {float(x.get('other_deduction') or 0):,.0f} Ks")
        return cls._result(message,rows)

    @classmethod
    def _finance(cls,query,text,permissions=None):
        if any(x in text for x in ("commission","ကော်မရှင်")):
            start,end=cls._date_range(query);rows=cls._employee_match(service.performance_report(start,end),query)
            total=sum(float(x.get("commission_amount") or 0) for x in rows)
            message=f"💹 **Employee Commission — {start} to {end}**\n\nEmployees: {len(rows)}\nCommission Total: {total:,.0f} Ks"
            if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: Rate {float(x.get('commission_rate') or 0):g}%, Target {float(x.get('target_amount') or 0):,.0f} Ks, Commission {float(x.get('commission_amount') or 0):,.0f} Ks" for x in rows[:20])
            return cls._result(message,rows)
        rows=cls._employee_match(service.list_advances(),query)
        if any(x in text for x in ("outstanding","ကျန်")):rows=[x for x in rows if x.get("status")=="Outstanding"]
        balance=sum(float(x.get("balance") or 0) for x in rows)
        message=f"💰 **Salary Advances**\n\nRecords: {len(rows)}\nOutstanding Balance: {balance:,.0f} Ks"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {float(x.get('balance') or 0):,.0f} Ks ({x['status']})" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _performance(cls,query,text,permissions=None):
        start,end=cls._date_range(query)
        if start==end:start=(date.fromisoformat(end)-timedelta(days=30)).isoformat()
        rows=cls._employee_match(service.performance_report(start,end),query)
        message=f"📈 **Employee Performance — {start} to {end}**\n\nEmployees: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: Sales {x['sale_count']}, Revenue {float(x['sales_total'] or 0):,.0f} Ks, Commission {float(x['commission_amount'] or 0):,.0f} Ks" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _cash_sessions(cls,query,text,permissions=None):
        rows=cls._employee_match(service.list_cash_sessions(),query)
        if "open" in text:rows=[x for x in rows if x.get("status")=="Open"]
        elif "closed" in text:rows=[x for x in rows if x.get("status")=="Closed"]
        message=f"💵 **Cash Sessions**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['status']}, Difference {float(x.get('difference') or 0):,.0f} Ks" for x in rows[:20])
        return cls._result(message,rows)
