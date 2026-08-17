"""Parse safe, read-only page navigation requests from AI Chat prompts."""

import re


class AINavigationRequest:
    NAVIGATION_WORDS=("open","go to","show page","view page","ဖွင့်","ဖွင့်","သွား","စာမျက်နှာ")
    EMPLOYEE_TABS=(
        ("cash_sessions",("cash session","cash-session","ငွေစာရင်း")),
        ("performance",("performance","စွမ်းဆောင်ရည်")),
        ("finance",("commission","advance","ကော်မရှင်","ကြိုတင်လစာ")),
        ("documents",("document","စာရွက်စာတမ်း")),
        ("payroll",("payroll","salary","လစာ")),
        ("attendance",("attendance","check-in","check in","check-out","check out","late","တက်ရောက်","အလုပ်ဝင်","အလုပ်ဆင်း","နောက်ကျ")),
        ("leave",("leave","ခွင့်")),
        ("shifts",("shift","အလုပ်ချိန်")),
        ("employees",("employee","employees","staff","ဝန်ထမ်း","profile")),
    )
    BUSINESS_PAGES=(
        ("inventory",("inventory","stock","စတော့")), ("products",("product","ပစ္စည်း")),
        ("receipts",("receipt","invoice","ပြေစာ")), ("customers",("customer","ဖောက်သည်")),
        ("expense",("expense","ကုန်ကျစရိတ်","အသုံးစရိတ်")),
        ("sales_summary",("sales summary","report","အရောင်းအစီရင်ခံစာ")),
        ("sales",("sales","checkout","အရောင်း")),
    )

    @classmethod
    def parse(cls,query):
        text=(query or "").lower()
        if not any(word in text for word in cls.NAVIGATION_WORDS):return None
        for tab,words in cls.EMPLOYEE_TABS:
            if any(word in text for word in words):return cls._employee_request(tab,text)
        for page,words in cls.BUSINESS_PAGES:
            if any(word in text for word in words):return {"page":page,"filters":{}}
        return None

    @classmethod
    def for_employee_module(cls,module):
        return {"page":"employees","tab":module or "employees","filters":{}}

    @classmethod
    def enrich(cls,request,context):
        if not request:return None
        enriched={**request,"filters":dict(request.get("filters") or {})}
        if enriched.get("page")=="employees":
            if context.employee_no:enriched["filters"].setdefault("employee",context.employee_no)
            if context.start_date:
                enriched["filters"].setdefault("start_date",context.start_date)
                enriched["filters"].setdefault("end_date",context.end_date or context.start_date)
        return enriched

    @staticmethod
    def _employee_request(tab,text):
        filters={};employee=re.search(r"\bEMP-\d+\b",text,re.I)
        if employee:filters["employee"]=employee.group(0).upper()
        for status in ("Present","Late","Incomplete","Absent","Half-day","Leave","Draft","Paid","Pending","Approved","Rejected","Open","Closed","Outstanding","Repaid"):
            if status.lower() in text:filters["status"]=status;break
        issue_words=(("Missing Check-in",("missing check-in","missing check in","check-in မရှိ","အလုပ်ဝင် မရှိ")),("Missing Check-out",("missing check-out","missing check out","check-out မရှိ","အလုပ်ဆင်း မရှိ")),("Check-in before Shift",("before shift","စောဝင်")),("Check-in after Shift",("after shift","နောက်ကျ")))
        for issue,words in issue_words:
            if any(word in text for word in words):filters["issue"]=issue;break
        return {"page":"employees","tab":tab,"filters":filters}
