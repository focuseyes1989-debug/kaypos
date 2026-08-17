import unittest
from unittest.mock import patch

from ui.ai_pages.ai_sales_summary_queries import AISalesSummaryQueryHandler


class _Cursor:
    def __init__(self,rows):self.rows=list(rows);self.executions=[]
    def execute(self,sql,params=()):self.executions.append((sql,params));return self
    def fetchone(self):return self.rows.pop(0)
    def fetchall(self):return self.rows.pop(0)


class _Connection:
    def __init__(self,rows):self.value=_Cursor(rows);self.closed=False
    def cursor(self):return self.value
    def close(self):self.closed=True


class TestAISalesSummaryPhase1(unittest.TestCase):
    def test_bilingual_conversational_intents(self):
        for query in ("ဒီနေ့ အရောင်းအကျဉ်းချုပ်ပြပါ","ဒီလ net sales ဘယ်လောက်လဲ","ဒီနေ့ transaction ဘယ်နှခုရှိလဲ","this month sales overview"):
            with self.subTest(query=query):self.assertTrue(AISalesSummaryQueryHandler.handles(query))

    def test_metric_collection_matches_page_definition(self):
        connection=_Connection([(1000,12,4),(100,),(50,)])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            metrics=AISalesSummaryQueryHandler.collect("2026-08-01","2026-08-18")
        self.assertEqual(metrics["gross_sales"],1000);self.assertEqual(metrics["net_sales"],900)
        self.assertEqual(metrics["average_sale"],225);self.assertEqual(metrics["items_sold"],12);self.assertEqual(metrics["refunds"],50)
        self.assertTrue(connection.closed)

    def test_permission_is_required(self):
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales"}):
            result=AISalesSummaryQueryHandler.handle("ဒီနေ့ အရောင်းအကျဉ်းချုပ်ပြပါ",8)
        self.assertIn("permission",result["message"].lower());self.assertEqual(result["data"],[])

    def test_comparison_calculates_all_sales_metrics(self):
        current={"gross_sales":150,"net_sales":135,"transactions":3,"items_sold":6,"average_sale":45,"discounts":15,"refunds":5}
        previous={"gross_sales":100,"net_sales":90,"transactions":2,"items_sold":4,"average_sale":45,"discounts":10,"refunds":10}
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales_summary"}),patch("ui.ai_pages.ai_sales_summary_queries.AIDashboardQueryHandler.comparison_periods",return_value=("2026-08-18","2026-08-18","2026-08-17","2026-08-17")),patch.object(AISalesSummaryQueryHandler,"collect",side_effect=[current,previous]):
            result=AISalesSummaryQueryHandler.handle("ဒီနေ့နဲ့ မနေ့က အရောင်းနှိုင်းယှဉ်ပေးပါ",1)
        self.assertEqual(result["type"],"sales_summary_comparison")
        self.assertEqual(result["changes"]["net_sales"]["Change %"],50)
        self.assertEqual(result["changes"]["refunds"]["Direction"],"down")

    def test_comparison_zero_baseline_is_marked_new(self):
        changes=AISalesSummaryQueryHandler.compare_metrics({"net_sales":100},{"net_sales":0})
        self.assertIsNone(changes["net_sales"]["Change %"])

    def test_product_and_category_analysis_intents(self):
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("ဒီလ ရောင်းအားအကောင်းဆုံး ပစ္စည်း ၅ မျိုးပြပါ"),"top_products")
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("မရောင်းရဆုံး product ပြပါ"),"low_products")
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("ဘယ် category က အရောင်းအများဆုံးလဲ"),"categories")
        self.assertEqual(AISalesSummaryQueryHandler._limit("top 5 products"),5)
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("Cash နဲ့ KPay ဘယ်ဟာပိုများလဲ"),"payments")

    def test_breakdown_collection_and_revenue_share(self):
        connection=_Connection([[('Tea',4,400),('Coffee',2,200)]])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            rows=AISalesSummaryQueryHandler.collect_breakdown("top_products","2026-08-01","2026-08-18",5)
        self.assertEqual(rows[0]["Label"],"Tea");self.assertEqual(rows[0]["Revenue"],400);self.assertTrue(connection.closed)

    def test_category_question_filters_exact_known_category(self):
        rows=[{"Label":"Drinks","Quantity":3,"Revenue":300},{"Label":"Food","Quantity":2,"Revenue":200}]
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales_summary"}),patch.object(AISalesSummaryQueryHandler,"collect_breakdown",return_value=rows),patch("ui.ai_pages.ai_sales_summary_queries.EmployeeQueryHandler._date_range",return_value=("2026-08-01","2026-08-18")):
            result=AISalesSummaryQueryHandler.handle("ဒီလ Drinks category ရောင်းအားဘယ်လောက်ရှိလဲ",1)
        self.assertEqual(len(result["data"]),1);self.assertEqual(result["data"][0]["Label"],"Drinks");self.assertEqual(result["data"][0]["Share %"],60)

    def test_payment_breakdown_uses_recorded_net_total(self):
        connection=_Connection([[('Cash',3,300),('KPay',2,200)]])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            rows=AISalesSummaryQueryHandler.collect_breakdown("payments","2026-08-01","2026-08-18")
        self.assertEqual(rows[0],{"Label":"Cash","Transactions":3,"Revenue":300.0})
        self.assertIn("SUM(s.total)",connection.value.executions[0][0])

    def test_payment_comparison_filters_requested_methods_and_keeps_overall_share(self):
        rows=[{"Label":"Cash","Transactions":4,"Revenue":400},{"Label":"KPay","Transactions":3,"Revenue":300},{"Label":"Credit","Transactions":3,"Revenue":300}]
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales_summary"}),patch.object(AISalesSummaryQueryHandler,"collect_breakdown",return_value=rows),patch("ui.ai_pages.ai_sales_summary_queries.EmployeeQueryHandler._date_range",return_value=("2026-08-01","2026-08-18")):
            result=AISalesSummaryQueryHandler.handle("Cash နဲ့ KPay ဘယ်ဟာပိုများလဲ",1)
        self.assertEqual([row["Label"] for row in result["data"]],["Cash","KPay"])
        self.assertEqual(result["data"][0]["Share %"],40)
        self.assertEqual(result["data"][1]["Share %"],30)

    def test_cashier_performance_collection_and_rank(self):
        raw=[('cashier1','EMP-0001','Ko Zay',3,300,6,10,5),('cashier2','EMP-0002','Ma Mya',2,200,3,0,0)]
        connection=_Connection([raw])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            rows=AISalesSummaryQueryHandler.collect_cashiers("2026-08-01","2026-08-18")
        self.assertEqual(rows[0]["Rank"],1);self.assertEqual(rows[0]["Average Sale"],100);self.assertEqual(rows[0]["Employee"],"Ko Zay")
        sql=connection.value.executions[0][0]
        self.assertIn("ss.transactions",sql);self.assertNotIn("column2",sql)

    def test_cashier_personal_scope_is_filtered_by_logged_in_username(self):
        row={"Rank":1,"Username":"cashier1","Employee No":"EMP-0001","Employee":"Ko Zay","Transactions":3,"Sales":300,"Items Sold":6,"Average Sale":100,"Discounts":10,"Refunds":5}
        context={"username":"cashier1","full_name":"Ko Zay"}
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales"}),patch("ui.ai_pages.ai_sales_summary_queries.EmployeeQueryHandler._date_range",return_value=("2026-08-01","2026-08-18")),patch("ui.ai_pages.ai_sales_summary_queries.AIDashboardQueryHandler._user_context",return_value=context),patch.object(AISalesSummaryQueryHandler,"collect_cashiers",return_value=[row]) as collect:
            result=AISalesSummaryQueryHandler.handle("my sales performance this month",8)
        self.assertEqual(result["scope"],"personal");collect.assert_called_once_with("2026-08-01","2026-08-18","cashier1")

    def test_company_cashier_ranking_requires_both_permissions(self):
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales_summary"}):
            result=AISalesSummaryQueryHandler.handle("ဒီလ အရောင်းအကောင်းဆုံး cashier သုံးယောက်ပြပါ",2)
        self.assertIn("permissions",result["message"].lower())

    def test_cashier_ranking_limit_is_understood(self):
        self.assertEqual(AISalesSummaryQueryHandler._cashier_limit("top 3 cashiers"),3)
        self.assertEqual(AISalesSummaryQueryHandler._cashier_limit("အကောင်းဆုံး ၅ ယောက်"),5)

    def test_daily_and_hourly_chart_intents(self):
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("ဒီလ daily sales trend ဂရပ်ပြပါ"),"daily_sales")
        self.assertEqual(AISalesSummaryQueryHandler._analysis_kind("ဒီနေ့ နာရီအလိုက် အရောင်းပြပါ"),"hourly_sales")

    def test_daily_chart_is_limited_to_31_days(self):
        connection=_Connection([[('2026-08-17',300,3)]])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            rows,start,end=AISalesSummaryQueryHandler.collect_trend("daily_sales","2026-01-01","2026-08-18")
        self.assertEqual((start,end),("2026-07-19","2026-08-18"));self.assertEqual(rows[0]["Sales"],300)

    def test_hourly_chart_formats_hour_labels(self):
        connection=_Connection([[(8,100,2),(19,300,3)]])
        with patch("ui.ai_pages.ai_sales_summary_queries.connect_db",return_value=connection),patch("ui.ai_pages.ai_sales_summary_queries.is_postgres_backend",return_value=False):
            rows,_start,_end=AISalesSummaryQueryHandler.collect_trend("hourly_sales","2026-08-18","2026-08-18")
        self.assertEqual([row["Hour"] for row in rows],["08:00","19:00"])

    def test_sales_alert_thresholds_and_evidence(self):
        current={"gross_sales":100,"net_sales":50,"transactions":5,"discounts":20,"refunds":10}
        previous={"net_sales":100};products=[{"Label":"Tea","Revenue":20}];previous_products=[{"Label":"Tea","Revenue":100}]
        payments=[{"Label":"Cash","Revenue":90},{"Label":"KPay","Revenue":10}]
        evidence={"largest_invoice":"INV-1","largest_sale":80,"average_sale":20,"transactions":5,"cashier":"cashier1","cashier_sales":100,"cashier_discounts":25,"cashier_transactions":5}
        alerts=AISalesSummaryQueryHandler.evaluate_alerts(current,previous,products,previous_products,payments,evidence,True)
        titles={row["Title"] for row in alerts}
        self.assertTrue({"Sales decline","High discount rate","High refund rate","Product sales drop","Payment concentration","Large transaction","Unusual cashier discounts"}.issubset(titles))
        self.assertEqual(alerts[0]["Severity"],"Critical")

    def test_no_sales_alert_detects_stopped_period(self):
        alerts=AISalesSummaryQueryHandler.evaluate_alerts({"gross_sales":0,"net_sales":0,"transactions":0,"discounts":0,"refunds":0},{"net_sales":500},[],[],[],{},False)
        self.assertEqual(alerts[0]["Title"],"No sales");self.assertEqual(alerts[0]["Severity"],"Critical")

    def test_sales_alert_intent_is_bilingual(self):
        self.assertTrue(AISalesSummaryQueryHandler._is_alert("ဒီနေ့ အရောင်းမှာ ပုံမှန်မဟုတ်တာရှိလား"))
        self.assertTrue(AISalesSummaryQueryHandler.handles("sales anomaly alert ပြပါ"))

    def test_explanation_intent_and_dimension_changes(self):
        self.assertTrue(AISalesSummaryQueryHandler._is_explanation("ဒီလ အရောင်း ဘာကြောင့်ကျသွားတာလဲ"))
        rows=AISalesSummaryQueryHandler._dimension_changes([{"Label":"Tea","Revenue":50}],[{"Label":"Tea","Revenue":100},{"Label":"Coffee","Revenue":40}],"Product","Revenue")
        values={row["Segment"]:row["Impact"] for row in rows}
        self.assertEqual(values["Tea"],-50);self.assertEqual(values["Coffee"],-40)

    def test_recommendations_are_separated_from_facts(self):
        current={"net_sales":50,"transactions":2,"average_sale":25,"gross_sales":100,"discounts":15,"refunds":10};previous={"net_sales":100,"transactions":4,"average_sale":25}
        rows=[{"Dimension":"Product","Segment":"Tea","Impact":-50}]
        suggestions=AISalesSummaryQueryHandler.recommendations(current,previous,rows)
        self.assertTrue(any("transaction" in item.lower() for item in suggestions));self.assertTrue(any("Tea" in item for item in suggestions))

    def test_authorized_handler_returns_period_and_metrics(self):
        metrics={"gross_sales":100,"net_sales":90,"transactions":2,"items_sold":3,"average_sale":45,"discounts":10,"refunds":0}
        with patch.object(AISalesSummaryQueryHandler,"_permissions",return_value={"sales_summary"}),patch.object(AISalesSummaryQueryHandler,"collect",return_value=metrics),patch("ui.ai_pages.ai_sales_summary_queries.EmployeeQueryHandler._date_range",return_value=("2026-08-18","2026-08-18")):
            result=AISalesSummaryQueryHandler.handle("ဒီနေ့ အရောင်းအကျဉ်းချုပ်ပြပါ",1)
        self.assertEqual(result["type"],"sales_summary_foundation");self.assertEqual(result["metrics"]["net_sales"],90);self.assertEqual(result["start_date"],"2026-08-18")
        self.assertEqual(result["widget_meta"]["discount_rate"],10)
        self.assertEqual(result["widget_meta"]["items_per_transaction"],1.5)


if __name__=="__main__":unittest.main()
