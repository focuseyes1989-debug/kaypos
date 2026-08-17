"""Session-only conversational context for AI Chat follow-up questions."""

import re

from ui.ai_pages.ai_employee_queries import EmployeeQueryHandler
from services import employee_service


class AIConversationContext:
    """Remember safe query entities during one visible chat session."""

    MODULE_WORDS = {
        "attendance": ("attendance", "check-in", "check in", "check-out", "check out", "late", "အလုပ်ဝင်", "အလုပ်ဆင်း", "တက်ရောက်", "နောက်ကျ"),
        "shifts": ("shift", "အလုပ်ချိန်"),
        "leave": ("leave", "ခွင့်"),
        "payroll": ("payroll", "salary", "လစာ"),
        "finance": ("commission", "advance", "ကော်မရှင်", "ကြိုတင်လစာ"),
        "performance": ("performance", "စွမ်းဆောင်ရည်"),
        "cash_sessions": ("cash session", "cash-session", "ငွေစာရင်း"),
        "employees": ("employee", "employees", "staff", "ဝန်ထမ်း", "profile", "phone", "ဖုန်း", "ရာထူး", "ဌာန"),
    }
    FOLLOW_UP_WORDS = (
        "only", "what about", "how about", "same", "those", "them", "his", "her",
        "missing", "before", "after", "late", "present", "absent", "incomplete",
        "ပဲပြ", "ပဲ ပြ", "ကရော", "အဲဒါ", "အဲ့ဒါ", "သူ့", "သူရဲ့", "ထဲက",
        "နောက်ကျ", "မရှိ", "စောဝင်", "အလုပ်ပျက်", "ရက်တွေ", "စာရင်းပဲ",
    )
    DATE_WORDS = (
        "today", "yesterday", "tomorrow", "this month", "last month", "current month",
        "ဒီနေ့", "ယနေ့", "မနေ့က", "မနက်ဖြန်", "ဒီလ", "ယခုလ", "ပြီးခဲ့တဲ့လ", "လွန်ခဲ့တဲ့လ",
    )

    def __init__(self):
        self.clear()

    def clear(self):
        self.employee_no = None
        self.employee_name = None
        self.module = None
        self.start_date = None
        self.end_date = None

    def resolve(self, query):
        raw=(query or "").strip()
        if not raw or raw.startswith("/"):
            return raw
        text=raw.lower();module=self._module(text)
        is_follow_up=any(word in text for word in self.FOLLOW_UP_WORDS)
        additions=[]

        # Pronouns and filter-only questions inherit the selected employee.
        if self.employee_no and not re.search(r"\bEMP-\d+\b",raw,re.I):
            explicit_employee=self._explicit_employee(raw)
            if not explicit_employee and (is_follow_up or (module and self._has_pronoun(text))):
                additions.append(self.employee_no)

        # A filter-only follow-up such as "နောက်ကျတဲ့ရက်တွေပဲပြ" needs its
        # previous Employee module to reach the correct query handler.
        if not module and is_follow_up and self.module:
            additions.append(self._module_keyword(self.module))
            module=self.module

        # Reuse the former period only when the follow-up did not provide one.
        if module and module==self.module and self.start_date and not self._has_date(text):
            additions.append(self.start_date if self.start_date==self.end_date else f"{self.start_date} to {self.end_date}")

        return " ".join([raw]+additions).strip()

    def update(self, raw_query, resolved_query, result):
        if not result or result.get("type")=="error":
            return
        text=(resolved_query or raw_query or "").lower()
        module=self._module(text)
        if result.get("type")=="employee_query" and module:
            previous_module=self.module
            self.module=module
            rows=result.get("data") or []
            employee_numbers={str(row.get("employee_no")) for row in rows if row.get("employee_no")}
            if len(employee_numbers)==1:
                self.employee_no=next(iter(employee_numbers))
                names={str(row.get("full_name")) for row in rows if row.get("full_name")}
                self.employee_name=next(iter(names),None)
            if self._has_date(text):
                self.start_date,self.end_date=EmployeeQueryHandler._date_range(resolved_query)
            elif previous_module and previous_module!=module:
                self.start_date=self.end_date=None

    @classmethod
    def _module(cls,text):
        for module,words in cls.MODULE_WORDS.items():
            if any(word in text for word in words):
                return module
        return None

    @staticmethod
    def _module_keyword(module):
        return {"shifts":"shift","cash_sessions":"cash session","finance":"advance"}.get(module,module)

    @staticmethod
    def _has_pronoun(text):
        return any(word in text for word in ("his","her","their","သူ့","သူရဲ့","ကရော","အဲဒါ","အဲ့ဒါ"))

    @classmethod
    def _has_date(cls,text):
        return bool(re.search(r"\b20\d{2}(?:-(?:0[1-9]|1[0-2]))?(?:-(?:0[1-9]|[12]\d|3[01]))?\b",text)) or any(word in text for word in cls.DATE_WORDS)

    def _explicit_employee(self,query):
        """Detect a newly named employee before inheriting the old one."""
        normalized=EmployeeQueryHandler._normalize(query)
        try:
            rows=employee_service.list_employees()
        except Exception:
            return None
        for row in rows:
            if str(row.get("employee_no") or "").upper() in str(query).upper():
                return row
            name=EmployeeQueryHandler._normalize(row.get("full_name"))
            tokens=[token for token in name.split() if len(token)>=2]
            if name and name in normalized:
                return row
            if any(token in normalized for token in tokens):
                return row
        return None

    def description(self):
        parts=[]
        if self.employee_no:parts.append(f"Employee: {self.employee_name or self.employee_no} ({self.employee_no})")
        if self.module:parts.append(f"Module: {self.module}")
        if self.start_date:parts.append(f"Period: {self.start_date}" if self.start_date==self.end_date else f"Period: {self.start_date} to {self.end_date}")
        return " | ".join(parts)
