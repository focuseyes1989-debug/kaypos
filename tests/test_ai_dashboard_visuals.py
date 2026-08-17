import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui.ai_pages.ai_chat_room import AIChatRoom
from ui.ai_pages.ai_chat_visuals import AIResultVisual


class _VisualBuilder:
    _compact_number = staticmethod(AIChatRoom._compact_number)


class TestAIDashboardVisuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @staticmethod
    def _result(include_restricted=True):
        metrics = {
            "net_sales": 1250000, "transactions": 18, "gross_profit": 450000,
            "expenses": 150000, "net_profit": 300000, "low_stock": 3,
            "out_of_stock": 1, "outstanding_credit": 200000 if include_restricted else None,
            "open_cash_sessions": 2 if include_restricted else None,
            "attendance_issues": 4 if include_restricted else None,
        }
        return {
            "type": "dashboard_summary", "metrics": metrics,
            "start_date": "2026-08-01", "end_date": "2026-08-17", "data": [],
        }

    def test_dashboard_visual_contains_modern_summary_cards(self):
        spec = AIChatRoom._build_business_visual(_VisualBuilder(), self._result())
        self.assertEqual(spec["title"], "Dashboard cards — 2026-08-01 to 2026-08-17")
        labels = {card["label"] for card in spec["cards"]}
        self.assertIn("Net Sales", labels)
        self.assertIn("Net Profit", labels)
        self.assertIn("Outstanding Credit", labels)
        self.assertIn("Attendance Issues", labels)
        self.assertTrue(all(card.get("color") for card in spec["cards"]))

        widget = AIResultVisual(spec)
        self.assertEqual(len(widget.card_frames), len(spec["cards"]))
        self.assertGreater(len(widget.card_frames), 4)
        widget.deleteLater()

    def test_restricted_cards_are_not_invented(self):
        spec = AIChatRoom._build_business_visual(_VisualBuilder(), self._result(False))
        labels = {card["label"] for card in spec["cards"]}
        self.assertNotIn("Outstanding Credit", labels)
        self.assertNotIn("Open Cash Sessions", labels)
        self.assertNotIn("Attendance Issues", labels)

    def test_personal_summary_hides_company_metrics_and_labels_scope(self):
        result=self._result(False);result.update({"scope":"personal","scope_label":"Cashier One"})
        result["metrics"].update({"expenses":None,"net_profit":None,"low_stock":None,"out_of_stock":None})
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        labels={card["label"] for card in spec["cards"]}
        self.assertTrue(spec["title"].startswith("Personal Dashboard — Cashier One"))
        self.assertNotIn("Expenses",labels)
        self.assertNotIn("Net Profit",labels)
        self.assertNotIn("Low / Out of Stock",labels)

    def test_negative_profit_uses_warning_color(self):
        result = self._result()
        result["metrics"]["net_profit"] = -1000
        spec = AIChatRoom._build_business_visual(_VisualBuilder(), result)
        card = next(card for card in spec["cards"] if card["label"] == "Net Profit")
        self.assertEqual(card["color"], "#d63031")

    def test_comparison_visual_shows_direction_and_period_bars(self):
        result = {
            "type": "dashboard_comparison", "start_date": "2026-08-17", "end_date": "2026-08-17",
            "changes": {
                "net_sales": {"Current": 150, "Previous": 100, "Change %": 50.0, "Direction": "up"},
                "gross_profit": {"Current": 40, "Previous": 50, "Change %": -20.0, "Direction": "down"},
                "expenses": {"Current": 10, "Previous": 20, "Change %": -50.0, "Direction": "down"},
                "net_profit": {"Current": 30, "Previous": 30, "Change %": 0.0, "Direction": "flat"},
                "transactions": {"Current": 3, "Previous": 0, "Change %": None, "Direction": "up"},
            },
        }
        spec = AIChatRoom._build_business_visual(_VisualBuilder(), result)
        values = {card["label"]: card["value"] for card in spec["cards"]}
        self.assertEqual(values["Sales change"], "↑ 50.0%")
        self.assertEqual(values["Transaction change"], "NEW")
        self.assertEqual(len(spec["bars"]), 6)

    def test_dashboard_trend_renders_line_chart(self):
        result = {"type":"dashboard_chart","chart_kind":"sales_expenses","data":[
            {"Date":"2026-08-16","Sales":100,"Expenses":20},
            {"Date":"2026-08-17","Sales":180,"Expenses":40},
        ]}
        spec = AIChatRoom._build_business_visual(_VisualBuilder(), result)
        self.assertEqual(len(spec["series"]), 2)
        widget = AIResultVisual(spec)
        self.assertTrue(hasattr(widget, "trend_chart"))
        widget.resize(700,300);widget.show();self.app.processEvents()
        self.assertFalse(widget.grab().isNull())
        widget.deleteLater()

    def test_dashboard_breakdown_uses_bar_chart(self):
        result={"type":"dashboard_chart","chart_kind":"payments","data":[{"Label":"Cash","Value":100},{"Label":"KPay","Value":80}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(len(spec["bars"]),2)
        widget=AIResultVisual(spec)
        self.assertTrue(hasattr(widget,"chart"));widget.deleteLater()

    def test_dashboard_alerts_render_severity_cards(self):
        result={"type":"dashboard_alerts","data":[
            {"Severity":"Critical","Title":"Net loss"},
            {"Severity":"Warning","Title":"Sales decline"},
            {"Severity":"Info","Title":"Open sessions"},
        ]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        values={card["label"]:card["value"] for card in spec["cards"]}
        self.assertEqual(values["Critical"],"1")
        self.assertEqual(values["Total Alerts"],"3")
        self.assertEqual(len(spec["bars"]),3)

    def test_change_explanation_renders_signed_evidence(self):
        result={"type":"dashboard_explanation","explanation_focus":"profit","data":[
            {"Dimension":"Category","Segment":"Drinks","Impact":100},
            {"Dimension":"Expense Category","Segment":"Rent","Impact":-60},
        ]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(len(spec["bars"]),2)
        self.assertEqual(spec["bars"][1]["display"],"-60 Ks")
        self.assertEqual(spec["bars"][1]["color"],"#d63031")

    def test_executive_digest_renders_key_cards(self):
        result={"type":"dashboard_digest","digest_kind":"weekly","payload":{"metrics":{"net_sales":1000,"gross_profit":400,"net_profit":250},"alerts":[{"Title":"Low stock"}]},"data":[]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        values={card["label"]:card["value"] for card in spec["cards"]}
        self.assertEqual(values["Net Sales"],"1.0K Ks")
        self.assertEqual(values["Alerts"],"1")


if __name__ == "__main__":
    unittest.main()
