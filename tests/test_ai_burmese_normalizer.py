import unittest

from ui.ai_pages.ai_burmese_normalizer import AIBurmeseNormalizer
from ui.ai_pages.ai_navigation import AINavigationRequest


class TestAIBurmeseNormalizer(unittest.TestCase):
    def test_myanmar_digits_work_in_employee_ids_and_dates(self):
        self.assertEqual(
            AIBurmeseNormalizer.normalize("EMP-၀၀၀၈ attendance ၂၀၂၆-၀၈-၀၁"),
            "EMP-0008 attendance 2026-08-01",
        )

    def test_common_burmese_and_english_aliases(self):
        cases = {
            "ကိုဇေ ဖုန်းနံပတ်": "ကိုဇေ ဖုန်းနံပါတ်",
            "အချိန်မီမရောက်တဲ့ ဝန်ထမ်း သုံးယောက်": "နောက်ကျတဲ့ ဝန်ထမ်း သုံးယောက်",
            "လစာကြိုယူ စာရင်း": "ကြိုတင်လစာ စာရင်း",
            "attendence summary": "attendance summary",
            "checkin မရှိ": "check-in မရှိ",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(AIBurmeseNormalizer.normalize(query), expected)

    def test_zero_width_and_spacing_are_removed(self):
        self.assertEqual(AIBurmeseNormalizer.normalize("ကို\u200bဇေ   ph"), "ကိုဇေ phone")

    def test_names_are_not_fuzzy_corrected(self):
        self.assertEqual(AIBurmeseNormalizer.normalize("မောင် Kyaw ph"), "မောင် Kyaw phone")

    def test_normalized_navigation_keeps_employee_filter(self):
        query = AIBurmeseNormalizer.normalize("EMP-၀၀၀၈ attendence page ဖွင့်")
        self.assertEqual(
            AINavigationRequest.parse(query),
            {"page": "employees", "tab": "attendance", "filters": {"employee": "EMP-0008"}},
        )


if __name__ == "__main__":
    unittest.main()
