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

    def test_sales_summary_phase_one_renders_metric_cards(self):
        result={"type":"sales_summary_foundation","start_date":"2026-08-01","end_date":"2026-08-18","metrics":{"gross_sales":1000,"net_sales":900,"transactions":4,"items_sold":12,"average_sale":225,"discounts":100,"refunds":50},"widget_meta":{"has_sales":True,"discount_rate":10,"refund_rate":5,"items_per_transaction":3},"data":[]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        values={card["label"]:card["value"] for card in spec["cards"]}
        self.assertEqual(values["Net Sales"],"900 Ks")
        self.assertEqual(values["Transactions"],"4")
        self.assertEqual(values["Refunds"],"50 Ks")
        self.assertEqual(values["Period Status"],"Sales recorded")
        self.assertEqual(len(spec["bars"]),4)
        self.assertEqual(next(card for card in spec["cards"] if card["label"]=="Refunds")["color"],"#d63031")

    def test_sales_summary_empty_period_has_clear_state(self):
        result={"type":"sales_summary_foundation","start_date":"2026-08-18","end_date":"2026-08-18","metrics":{"gross_sales":0,"net_sales":0,"transactions":0,"items_sold":0,"average_sale":0,"discounts":0,"refunds":0},"widget_meta":{"has_sales":False},"data":[]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        status=next(card for card in spec["cards"] if card["label"]=="Period Status")
        self.assertEqual(status["value"],"No sales")
        widget=AIResultVisual(spec)
        self.assertEqual(len(widget.card_frames),8);widget.deleteLater()

    def test_sales_summary_comparison_uses_direction_cards_and_period_bars(self):
        result={"type":"sales_summary_comparison","start_date":"2026-08-18","end_date":"2026-08-18","changes":{"net_sales":{"Current":150,"Previous":100,"Change %":50,"Direction":"up"},"transactions":{"Current":3,"Previous":2,"Change %":50,"Direction":"up"},"items_sold":{"Current":6,"Previous":4,"Change %":50,"Direction":"up"},"average_sale":{"Current":50,"Previous":50,"Change %":0,"Direction":"flat"},"discounts":{"Current":20,"Previous":10,"Change %":100,"Direction":"up"},"refunds":{"Current":5,"Previous":10,"Change %":-50,"Direction":"down"}},"data":[]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        cards={card["label"]:card for card in spec["cards"]}
        self.assertEqual(cards["Net Sales"]["value"],"↑ 50.0%")
        self.assertEqual(cards["Discounts"]["color"],"#d63031")
        self.assertEqual(cards["Refunds"]["color"],"#00a86b")
        self.assertEqual(len(spec["bars"]),8)

    def test_sales_summary_breakdown_renders_share_bars(self):
        result={"type":"sales_summary_breakdown","analysis_kind":"top_products","total_revenue":600,"data":[{"Label":"Tea","Quantity":4,"Revenue":400,"Share %":66.7},{"Label":"Coffee","Quantity":2,"Revenue":200,"Share %":33.3}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(spec["title"],"Top-selling products");self.assertEqual(len(spec["bars"]),2)
        self.assertIn("66.7%",spec["bars"][0]["display"])

    def test_payment_breakdown_renders_transaction_widget(self):
        result={"type":"sales_summary_breakdown","analysis_kind":"payments","total_revenue":700,"data":[{"Label":"Cash","Transactions":4,"Revenue":400,"Share %":40},{"Label":"KPay","Transactions":3,"Revenue":300,"Share %":30}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        cards={card["label"]:card["value"] for card in spec["cards"]}
        self.assertEqual(spec["title"],"Sales by payment type");self.assertEqual(cards["Transactions"],"7")

    def test_cashier_performance_renders_ranked_sales(self):
        result={"type":"sales_summary_breakdown","analysis_kind":"cashiers","scope":"business","data":[{"Rank":1,"Employee":"Ko Zay","Transactions":3,"Sales":300},{"Rank":2,"Employee":"Ma Mya","Transactions":2,"Sales":200}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(spec["title"],"Cashier sales performance");self.assertEqual(spec["bars"][0]["label"],"#1 Ko Zay")

    def test_sales_summary_trend_renders_two_series(self):
        result={"type":"sales_summary_chart","chart_kind":"daily_sales","data":[{"Date":"2026-08-17","Sales":100,"Transactions":2},{"Date":"2026-08-18","Sales":200,"Transactions":3}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(spec["title"],"Daily sales trend");self.assertEqual(len(spec["series"]),2)
        widget=AIResultVisual(spec);self.assertTrue(hasattr(widget,"trend_chart"));widget.deleteLater()

    def test_sales_alerts_render_severity_widgets(self):
        result={"type":"sales_summary_alerts","data":[{"Severity":"Critical","Title":"High refund rate"},{"Severity":"Warning","Title":"Sales decline"},{"Severity":"Info","Title":"Payment concentration"}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        values={card["label"]:card["value"] for card in spec["cards"]}
        self.assertEqual(values["Total Alerts"],"3");self.assertEqual(len(spec["bars"]),3)

    def test_sales_explanation_renders_signed_evidence(self):
        result={"type":"sales_summary_explanation","recommendations":["Review Tea"],"data":[{"Dimension":"Product","Segment":"Tea","Impact":100},{"Dimension":"Metric","Segment":"Refund impact","Impact":-40}]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(spec["title"],"Sales change evidence");self.assertEqual(spec["bars"][1]["color"],"#d63031")

    def test_sales_digest_renders_export_ready_cards(self):
        result={"type":"sales_summary_digest","digest_kind":"weekly","scope":"business","payload":{"metrics":{"net_sales":1000,"transactions":5,"items_sold":10,"average_sale":200},"changes":{"net_sales":{"Change %":10},"transactions":{"Change %":0},"items_sold":{"Change %":25},"average_sale":{"Change %":10}}},"data":[]}
        spec=AIChatRoom._build_business_visual(_VisualBuilder(),result)
        self.assertEqual(spec["title"],"Weekly sales digest");self.assertEqual(len(spec["cards"]),4)


if __name__ == "__main__":
    unittest.main()
