import unittest
from datetime import date
from unittest.mock import patch

from ui.ai_pages.ai_dashboard_queries import AIDashboardQueryHandler


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executions = []

    def execute(self, _sql, _params=()):
        self.executions.append((_sql,_params))
        return self

    def fetchone(self):
        return self.rows.pop(0)

    def fetchall(self):
        return self.rows.pop(0)


class _Connection:
    def __init__(self, rows):
        self.cursor_value = _Cursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


class TestAIDashboardQueries(unittest.TestCase):
    def test_dashboard_query_detection(self):
        self.assertTrue(AIDashboardQueryHandler.handles("ဒီလ dashboard summary ပြပါ"))
        self.assertTrue(AIDashboardQueryHandler.handles("ဒက်ရှ်ဘုတ် အခြေအနေ ပြ"))
        self.assertFalse(AIDashboardQueryHandler.handles("ဒီလ employee attendance"))
        self.assertTrue(AIDashboardQueryHandler.handles("my sales summary ပြပါ"))
        self.assertTrue(AIDashboardQueryHandler.handles("ကိုယ်ပိုင်အရောင်း အခြေအနေပြပါ"))

    def test_cashier_is_automatically_routed_to_personal_scope(self):
        metrics={"gross_sales":100,"discounts":0,"refunds":0,"net_sales":100,"transactions":1,"cogs":40,"gross_profit":60,"expenses":None,"net_profit":None,"outstanding_credit":None,"low_stock":None,"out_of_stock":None,"open_cash_sessions":0,"attendance_issues":None,"attendance_records":None}
        context={"username":"cashier1","full_name":"Cashier One","employee_id":8}
        with patch.object(AIDashboardQueryHandler,"_permissions",return_value={"sales"}), \
             patch.object(AIDashboardQueryHandler,"_user_context",return_value=context), \
             patch.object(AIDashboardQueryHandler,"collect_personal",return_value=metrics) as collect:
            result=AIDashboardQueryHandler.handle("dashboard summary ပြပါ",7)
        self.assertEqual(result["scope"],"personal")
        self.assertEqual(result["scope_label"],"Cashier One")
        collect.assert_called_once()

    def test_personal_collection_filters_by_logged_in_username(self):
        connection=_Connection([(1000,2),(100,),(50,),(400,),(1,),(10,2)])
        context={"username":"cashier1","employee_id":8}
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db",return_value=connection), \
             patch("ui.ai_pages.ai_dashboard_queries.table_exists",return_value=True), \
             patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend",return_value=False):
            metrics=AIDashboardQueryHandler.collect_personal("2026-08-01","2026-08-17",context)
        sale_queries=connection.cursor_value.executions[:4]
        self.assertTrue(all(params[0]=="cashier1" for _sql,params in sale_queries))
        self.assertEqual(metrics["net_sales"],850)
        self.assertEqual(metrics["gross_profit"],450)
        self.assertIsNone(metrics["expenses"])
        self.assertIsNone(metrics["outstanding_credit"])
        self.assertEqual(metrics["attendance_issues"],2)

    def test_fair_comparison_periods(self):
        today = date(2026, 8, 17)
        self.assertEqual(
            AIDashboardQueryHandler.comparison_periods("ဒီနေ့နဲ့ မနေ့က dashboard နှိုင်းယှဉ်ပါ", today),
            ("2026-08-17", "2026-08-17", "2026-08-16", "2026-08-16"),
        )
        self.assertEqual(
            AIDashboardQueryHandler.comparison_periods("ဒီလ dashboard comparison", today),
            ("2026-08-01", "2026-08-17", "2026-07-01", "2026-07-17"),
        )
        self.assertEqual(
            AIDashboardQueryHandler.comparison_periods("2026-08-10 to 2026-08-17 dashboard compare", today),
            ("2026-08-10", "2026-08-17", "2026-08-02", "2026-08-09"),
        )

    def test_comparison_changes_and_zero_baseline(self):
        changes = AIDashboardQueryHandler.compare_metrics(
            {"net_sales": 150, "transactions": 3, "gross_profit": 20, "expenses": 5, "net_profit": 15, "discounts": 0, "refunds": 0, "cogs": 130, "attendance_issues": None},
            {"net_sales": 100, "transactions": 0, "gross_profit": 25, "expenses": 10, "net_profit": 15, "discounts": 0, "refunds": 0, "cogs": 75, "attendance_issues": None},
        )
        self.assertEqual(changes["net_sales"]["Change %"], 50.0)
        self.assertEqual(changes["gross_profit"]["Direction"], "down")
        self.assertIsNone(changes["transactions"]["Change %"])
        self.assertNotIn("attendance_issues", changes)

    def test_comparison_handler_collects_both_periods(self):
        current = {"net_sales": 200, "transactions": 2, "discounts": 0, "refunds": 0, "cogs": 50, "gross_profit": 150, "expenses": 20, "net_profit": 130, "attendance_issues": None}
        previous = {"net_sales": 100, "transactions": 1, "discounts": 0, "refunds": 0, "cogs": 30, "gross_profit": 70, "expenses": 10, "net_profit": 60, "attendance_issues": None}
        with patch.object(AIDashboardQueryHandler, "_permissions", return_value={"dashboard"}), \
             patch.object(AIDashboardQueryHandler, "comparison_periods", return_value=("2026-08-17", "2026-08-17", "2026-08-16", "2026-08-16")), \
             patch.object(AIDashboardQueryHandler, "collect", side_effect=[current, previous]) as collect:
            result = AIDashboardQueryHandler.handle("dashboard today vs yesterday compare", 1)
        self.assertEqual(result["type"], "dashboard_comparison")
        self.assertEqual(collect.call_count, 2)
        self.assertEqual(result["changes"]["net_sales"]["Change %"], 100.0)

    def test_chart_intent_routing(self):
        cases = {
            "dashboard payment breakdown chart": "payments",
            "dashboard top products chart": "top_products",
            "dashboard sales category chart": "categories",
            "dashboard transaction trend": "transactions",
            "dashboard sales vs expense graph": "sales_expenses",
            "dashboard profit trend": "profit",
            "dashboard daily chart": "daily_sales",
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertTrue(AIDashboardQueryHandler.handles(query))
                self.assertEqual(AIDashboardQueryHandler._chart_kind(query), expected)

    def test_daily_chart_data_is_merged_and_limited(self):
        connection = _Connection([
            [("2026-07-18", 100, 2), ("2026-08-17", 200, 3)],
            [("2026-08-17", 40)],
            [("2026-08-17", 80)],
        ])
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db", return_value=connection), \
             patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend", return_value=False):
            data, start, end = AIDashboardQueryHandler.collect_chart("profit", "2026-01-01", "2026-08-17")
        self.assertEqual((start, end), ("2026-07-18", "2026-08-17"))
        august = next(row for row in data if row["Date"] == "2026-08-17")
        self.assertEqual(august["Gross Profit"], 120)
        self.assertEqual(august["Net Profit"], 80)
        self.assertTrue(connection.closed)

    def test_dashboard_permission_is_required(self):
        with patch.object(AIDashboardQueryHandler, "_permissions", return_value=set()), \
             patch.object(AIDashboardQueryHandler, "_user_context", return_value={}):
            result = AIDashboardQueryHandler.handle("ဒီနေ့ dashboard data ပြပါ", 10)
        self.assertIn("permission", result["message"].lower())
        self.assertEqual(result["data"], [])

    def test_fixed_metric_collection_and_permission_scoping(self):
        connection = _Connection([
            (1000, 2), (100,), (50,), (400,), (200,), (3,), (1,),
            (500,), (2,), (20, 4),
        ])
        permissions = {"dashboard", "credit", "cash_sessions", "attendance"}
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db", return_value=connection), \
             patch("ui.ai_pages.ai_dashboard_queries.table_exists", return_value=True), \
             patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend", return_value=False):
            metrics = AIDashboardQueryHandler.collect("2026-08-01", "2026-08-17", permissions)
        self.assertEqual(metrics["net_sales"], 850)
        self.assertEqual(metrics["gross_profit"], 450)
        self.assertEqual(metrics["net_profit"], 250)
        self.assertEqual(metrics["outstanding_credit"], 500)
        self.assertEqual(metrics["open_cash_sessions"], 2)
        self.assertEqual(metrics["attendance_issues"], 4)
        self.assertEqual(metrics["attendance_records"], 20)
        self.assertTrue(connection.closed)

    def test_restricted_metrics_are_omitted(self):
        connection = _Connection([(0, 0), (0,), (0,), (0,), (0,), (0,), (0,)])
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db", return_value=connection), \
             patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend", return_value=False):
            metrics = AIDashboardQueryHandler.collect("2026-08-17", "2026-08-17", {"dashboard"})
        self.assertIsNone(metrics["outstanding_credit"])
        self.assertIsNone(metrics["open_cash_sessions"])
        self.assertIsNone(metrics["attendance_issues"])
        self.assertIsNone(metrics["attendance_records"])

    def test_operational_alert_thresholds_and_severity(self):
        current={"net_sales":50,"gross_sales":100,"expenses":80,"gross_profit":-10,"net_profit":-90,"refunds":10,
                 "out_of_stock":2,"low_stock":3,"attendance_records":20,"attendance_issues":6,"open_cash_sessions":1,"outstanding_credit":500}
        previous={"net_sales":100,"expenses":40,"gross_profit":30}
        alerts=AIDashboardQueryHandler.evaluate_alerts(current,previous)
        titles={row["Title"] for row in alerts}
        self.assertTrue({"Sales decline","Expense increase","Net loss","High refund rate","Out of stock","Attendance issues"}.issubset(titles))
        self.assertEqual(alerts[0]["Severity"],"Critical")
        self.assertEqual(next(row for row in alerts if row["Title"]=="Attendance issues")["Target"],"employees")

    def test_no_alerts_for_healthy_or_empty_metrics(self):
        current={"net_sales":100,"gross_sales":100,"expenses":10,"gross_profit":40,"net_profit":30,"refunds":0,"out_of_stock":0,"low_stock":0,
                 "attendance_records":0,"attendance_issues":0,"open_cash_sessions":0,"outstanding_credit":0}
        self.assertEqual(AIDashboardQueryHandler.evaluate_alerts(current,current),[])

    def test_explanation_intent_and_permission_boundary(self):
        self.assertTrue(AIDashboardQueryHandler._is_explanation("dashboard sales ဘာကြောင့်ကျတာလဲ"))
        self.assertEqual(AIDashboardQueryHandler._explanation_focus("dashboard expense ဘာလို့များတာလဲ"),"expenses")
        with patch.object(AIDashboardQueryHandler,"_permissions",return_value={"dashboard"}):
            result=AIDashboardQueryHandler.handle("dashboard profit ဘာကြောင့်ကျတာလဲ",1)
        self.assertIn("requires",result["message"])
        self.assertEqual(result["data"],[])

    def test_sales_explanation_calculates_segment_changes(self):
        connection=_Connection([
            [("Tea",100)],[("Tea",60)],
            [("Drinks",100)],[("Drinks",60)],
            [("Cash",80)],[("Cash",90)],
            [("admin",80)],[("admin",90)],
        ])
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend",return_value=False):
            rows=AIDashboardQueryHandler.collect_explanation("sales","2026-08-17","2026-08-17","2026-08-16","2026-08-16")
        tea=next(row for row in rows if row["Dimension"]=="Product")
        cash=next(row for row in rows if row["Dimension"]=="Payment")
        self.assertEqual(tea["Impact"],40)
        self.assertEqual(cash["Impact"],-10)
        self.assertTrue(connection.closed)

    def test_profit_explanation_reverses_expense_impact(self):
        empty=[]
        connection=_Connection([empty,empty,empty,empty,empty,empty,empty,empty,[("Rent",100)],[("Rent",40)],empty,empty,empty,empty])
        with patch("ui.ai_pages.ai_dashboard_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_dashboard_queries.is_postgres_backend",return_value=False):
            rows=AIDashboardQueryHandler.collect_explanation("profit","2026-08-17","2026-08-17","2026-08-16","2026-08-16")
        rent=next(row for row in rows if row["Segment"]=="Rent")
        self.assertEqual(rent["Change"],60)
        self.assertEqual(rent["Impact"],-60)


if __name__ == "__main__":
    unittest.main()
