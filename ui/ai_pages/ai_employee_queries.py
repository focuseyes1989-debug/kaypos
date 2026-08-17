"""Permission-aware Employee Management queries for AI Chat."""

import re
import unicodedata
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
        "ဝန်ထမ်း", "အလုပ်ဝင်", "အလုပ်ဆင်း", "တက်ရောက်", "အလုပ်ချိန်",
        "လစာ", "ခွင့်", "ကော်မရှင်", "ကြိုတင်လစာ", "စွမ်းဆောင်ရည်",
        "ဖုန်းနံပါတ်", "ဖုန်း", "ဆက်သွယ်ရန်နံပါတ်",
    )
    NAME_STOP_WORDS = DOMAIN_WORDS + (
        "summary", "list", "detail", "details", "today", "yesterday", "tomorrow",
        "missing", "late", "before", "after", "approved", "pending", "rejected",
        "open", "closed", "outstanding", "paid", "unpaid", "draft", "for", "of",
        "show", "find", "search", "what", "when", "how", "is", "the",
        "phone number", "phone", "mobile", "contact number", "ph",
        "ဒီနေ့", "ယနေ့", "မနေ့က", "စာရင်း", "အကျဉ်းချုပ်", "ရှာ", "ပြပါ",
        "ဘယ်သူ", "ဘယ်လောက်", "မရှိ", "ရှိ", "စောဝင်", "နောက်ကျ",
        "ဖုန်းနံပါတ်", "ဖုန်း", "ဆက်သွယ်ရန်နံပါတ်", "မှ", "ရဲ့", "၏",
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
            return getattr(cls,f"_{view}")(query,text)
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

    @staticmethod
    def _normalize(value):
        value=unicodedata.normalize("NFKC",str(value or "")).casefold()
        return " ".join(re.sub(r"[^\w\u1000-\u109f]+"," ",value).split())

    @classmethod
    def _employee_search_term(cls,query):
        text=cls._normalize(query)
        text=re.sub(r"\bemp\s*\d+\b|\b20\d{2}[ -]\d{1,2}(?:[ -]\d{1,2})?\b|\b\d{1,2}[ ./-]\d{1,2}[ ./-]\d{4}\b"," ",text,flags=re.I)
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
    def _employees(cls,query,text):
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

    @classmethod
    def _attendance(cls,query,text):
        day=cls._date(query);rows=cls._employee_match(service.list_attendance(day),query)
        title="Attendance"
        if any(x in text for x in ("missing check-in","missing check in","no check-in","check-in မရှိ","အလုပ်ဝင် မရှိ")):
            rows=[x for x in rows if not x.get("check_in")];title="Missing Check-in"
        elif any(x in text for x in ("missing check-out","missing check out","no check-out","check-out မရှိ","အလုပ်ဆင်း မရှိ")):
            rows=[x for x in rows if not x.get("check_out")];title="Missing Check-out"
        elif any(x in text for x in ("before shift","စောဝင်")):
            rows=[x for x in rows if x.get("check_in") and x.get("shift_start") and str(x["check_in"])[:5]<str(x["shift_start"])[:5]];title="Check-in Before Shift"
        elif any(x in text for x in ("late","after shift","နောက်ကျ")):
            rows=[x for x in rows if x.get("status")=="Late" or (x.get("check_in") and x.get("shift_start") and str(x["check_in"])[:5]>str(x["shift_start"])[:5])];title="Late / After Shift"
        message=f"🕒 **{title} — {day}**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x.get('check_in') or '—'} / {x.get('check_out') or '—'} ({x.get('status')})" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _shifts(cls,query,text):
        rows=cls._employee_match(service.list_employee_shift_assignments(),query)
        message=f"🗓️ **Employee Shift Assignments**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['shift_name']} ({x['start_time']}–{x['end_time']}), from {x['effective_from']}" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _leave(cls,query,text):
        status="Pending" if any(x in text for x in ("pending","စောင့်")) else "Approved" if any(x in text for x in ("approved","အတည်ပြု")) else "Rejected" if "rejected" in text else "All"
        rows=cls._employee_match(service.list_leave(status),query)
        message=f"🏖️ **{status} Leave Requests**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['leave_type']} ({x['start_date']} to {x['end_date']}) — {x['status']}" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _payroll(cls,query,text):
        match=re.search(r"\b(20\d{2}-(?:0[1-9]|1[0-2]))\b",query or "");period=match.group(1) if match else date.today().strftime("%Y-%m")
        rows=cls._employee_match(service.list_payrolls(period),query)
        if "paid" in text:rows=[x for x in rows if x.get("status")=="Paid"]
        elif any(x in text for x in ("draft","unpaid","မပေး")):rows=[x for x in rows if x.get("status")=="Draft"]
        total=sum(float(x.get("net_salary") or 0) for x in rows)
        message=f"💵 **Payroll — {period}**\n\nRecords: {len(rows)}\nNet Total: {total:,.0f} Ks"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {float(x.get('net_salary') or 0):,.0f} Ks ({x['status']})" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _finance(cls,query,text):
        rows=cls._employee_match(service.list_advances(),query)
        if any(x in text for x in ("outstanding","ကျန်")):rows=[x for x in rows if x.get("status")=="Outstanding"]
        balance=sum(float(x.get("balance") or 0) for x in rows)
        message=f"💰 **Salary Advances**\n\nRecords: {len(rows)}\nOutstanding Balance: {balance:,.0f} Ks"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {float(x.get('balance') or 0):,.0f} Ks ({x['status']})" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _performance(cls,query,text):
        end=cls._date(query);start=(date.fromisoformat(end)-timedelta(days=30)).isoformat();rows=cls._employee_match(service.performance_report(start,end),query)
        message=f"📈 **Employee Performance — {start} to {end}**\n\nEmployees: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: Sales {x['sale_count']}, Revenue {float(x['sales_total'] or 0):,.0f} Ks, Commission {float(x['commission_amount'] or 0):,.0f} Ks" for x in rows[:20])
        return cls._result(message,rows)

    @classmethod
    def _cash_sessions(cls,query,text):
        rows=cls._employee_match(service.list_cash_sessions(),query)
        if "open" in text:rows=[x for x in rows if x.get("status")=="Open"]
        elif "closed" in text:rows=[x for x in rows if x.get("status")=="Closed"]
        message=f"💵 **Cash Sessions**\n\nTotal: {len(rows)}"
        if rows:message+="\n\n"+"\n".join(f"• {x['employee_no']} — {x['full_name']}: {x['status']}, Difference {float(x.get('difference') or 0):,.0f} Ks" for x in rows[:20])
        return cls._result(message,rows)
