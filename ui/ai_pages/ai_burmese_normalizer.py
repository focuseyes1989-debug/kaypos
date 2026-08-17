"""Conservative Burmese/English query normalization for AI Chat routing."""

import re
import unicodedata
from difflib import SequenceMatcher


class AIBurmeseNormalizer:
    """Normalize commands without fuzzy-changing employee names or business data."""

    MYANMAR_DIGITS = str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")
    ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")

    # Variants map to terms already understood by the guarded query handlers.
    PHRASE_ALIASES = (
        ("ဆက်သွယ်ရမယ့်နံပါတ်", "ဖုန်းနံပါတ်"),
        ("ဆက်သွယ်ရမည့်နံပါတ်", "ဖုန်းနံပါတ်"),
        ("ဆက်သွယ်ရန်ဖုန်း", "ဖုန်းနံပါတ်"),
        ("ဖုန်း နံပါတ်", "ဖုန်းနံပါတ်"),
        ("ဖုန်းနံပတ်", "ဖုန်းနံပါတ်"),
        ("ဖုန်းနပါတ်", "ဖုန်းနံပါတ်"),
        ("အချိန်မီမရောက်", "နောက်ကျ"),
        ("အချိန်မှီမရောက်", "နောက်ကျ"),
        ("ရုံးနောက်ကျ", "နောက်ကျ"),
        ("အလုပ်မတက်", "အလုပ်ပျက်"),
        ("အလုပ်မလာ", "အလုပ်ပျက်"),
        ("မတက်ရောက်", "အလုပ်ပျက်"),
        ("လစာကြိုယူ", "ကြိုတင်လစာ"),
        ("လစာကြိုထုတ်", "ကြိုတင်လစာ"),
        ("ကြိုလစာ", "ကြိုတင်လစာ"),
        ("အလုပ်ဝင်ချိန်", "check-in"),
        ("အလုပ်ဆင်းချိန်", "check-out"),
        ("check in", "check-in"),
        ("check out", "check-out"),
        ("checkin", "check-in"),
        ("checkout", "check-out"),
        ("ခွင့်", "ခွင့်"),
        ("ဖွင့်", "ဖွင့်"),
        ("ယခုလ", "ဒီလ"),
    )

    ENGLISH_ALIASES = {
        "ph": "phone",
        "phon": "phone",
        "fone": "phone",
        "attendence": "attendance",
        "attandance": "attendance",
        "payrol": "payroll",
        "salery": "salary",
        "emploee": "employee",
        "employe": "employee",
        "commision": "commission",
        "perfomance": "performance",
    }

    # Fuzzy correction is deliberately limited to standalone routing words.
    ROUTING_WORDS = (
        "employee", "employees", "attendance", "payroll", "salary", "leave",
        "shift", "commission", "advance", "performance", "phone", "profile",
        "open", "search", "summary", "business", "sales",
    )

    @classmethod
    def normalize(cls, query):
        text = unicodedata.normalize("NFKC", str(query or ""))
        text = cls.ZERO_WIDTH.sub("", text).translate(cls.MYANMAR_DIGITS)
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"[\t\r\n]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        for variant, canonical in sorted(cls.PHRASE_ALIASES, key=lambda item: len(item[0]), reverse=True):
            text = re.sub(re.escape(variant), canonical, text, flags=re.IGNORECASE)
        text = cls._normalize_english_words(text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _normalize_english_words(cls, text):
        def replace(match):
            word = match.group(0)
            lower = word.lower()
            if lower in cls.ENGLISH_ALIASES:
                return cls.ENGLISH_ALIASES[lower]
            # Do not guess short words, identifiers, names, or arbitrary prose.
            if len(lower) < 5 or any(char.isdigit() for char in lower):
                return word
            candidates = [known for known in cls.ROUTING_WORDS if abs(len(known) - len(lower)) <= 1]
            scored = [(SequenceMatcher(None, lower, known).ratio(), known) for known in candidates]
            if not scored:
                return word
            score, known = max(scored)
            return known if score >= 0.88 else word

        return re.sub(r"[A-Za-z]+", replace, text)
