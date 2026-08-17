import unittest
from datetime import date
from unittest.mock import patch

from ui.ai_pages.ai_sales_summary_governance import SalesSummaryGovernance,SalesSummaryDigestService,SalesSummaryDigestScheduler


class _Cursor:
    def __init__(self,rows=()):self.rows=list(rows);self.executions=[]
    def execute(self,sql,params=()):self.executions.append((sql,params));return self
    def fetchone(self):return self.rows.pop(0) if self.rows else None


class _Connection:
    def __init__(self,rows=()):self.value=_Cursor(rows);self.committed=False;self.closed=False
    def cursor(self):return self.value
    def commit(self):self.committed=True
    def rollback(self):pass
    def close(self):self.closed=True


class TestSalesSummaryGovernance(unittest.TestCase):
    def test_provenance_identifies_scope_sources_and_time(self):
        result={"type":"sales_summary_foundation","message":"Sales","scope":"business","start_date":"2026-08-18","end_date":"2026-08-18"}
        SalesSummaryGovernance.enrich(result)
        self.assertEqual(result["provenance"]["scope"],"business");self.assertIn("sales",result["provenance"]["sources"]);self.assertIn("Generated:",result["message"])

    def test_audit_stores_hash_not_raw_query_or_rows(self):
        schema=_Connection();insert=_Connection();result={"type":"sales_summary_chart","scope":"personal","start_date":"2026-08-01","end_date":"2026-08-18","data":[{"employee":"Sensitive Name"}]};SalesSummaryGovernance.enrich(result)
        with patch("ui.ai_pages.ai_sales_summary_governance.connect_db",side_effect=[schema,insert]):SalesSummaryGovernance.record("Sensitive Name sales",8,result,.125,True)
        _sql,params=insert.value.executions[0]
        self.assertEqual(len(params[1]),64);self.assertNotIn("Sensitive Name",str(params));self.assertEqual(params[3],"personal")

    def test_personal_digest_metrics_use_only_username(self):
        row={"Sales":300,"Discounts":20,"Transactions":3,"Items Sold":6,"Average Sale":100,"Refunds":5}
        with patch("ui.ai_pages.ai_sales_summary_governance.AISalesSummaryQueryHandler.collect_cashiers",return_value=[row]) as collect:
            metrics=SalesSummaryDigestService.metrics("2026-08-01","2026-08-18","personal",{"username":"cashier1"})
        collect.assert_called_once_with("2026-08-01","2026-08-18","cashier1");self.assertEqual(metrics["net_sales"],300);self.assertEqual(metrics["gross_sales"],320)

    def test_scheduler_uses_completed_periods_for_admin(self):
        with patch.object(SalesSummaryDigestScheduler,"enabled",return_value=True),patch.object(SalesSummaryGovernance,"permissions",return_value={"sales_summary"}),patch.object(SalesSummaryGovernance,"context",return_value={"username":"admin"}),patch.object(SalesSummaryDigestService,"generate",return_value={}) as generate:
            SalesSummaryDigestScheduler.run_due(1,"Admin",date(2026,8,18))
        periods=[call.args[1:3] for call in generate.call_args_list]
        self.assertEqual(periods[0],("2026-08-17","2026-08-17"));self.assertEqual(periods[1],("2026-08-10","2026-08-16"));self.assertEqual(periods[2],("2026-07-01","2026-07-31"))

    def test_cashier_cannot_read_company_audit(self):
        with patch.object(SalesSummaryGovernance,"permissions",return_value={"sales"}),patch.object(SalesSummaryGovernance,"context",return_value={"role":"Cashier"}):
            result=SalesSummaryGovernance.audit_history("sales AI audit history",8)
        self.assertIn("Admin or Manager",result["message"])

    def test_viewer_cannot_generate_management_sales_digest(self):
        with patch.object(SalesSummaryGovernance,"permissions",return_value={"sales_summary"}),patch.object(SalesSummaryGovernance,"context",return_value={"role":"Viewer"}):
            result=SalesSummaryDigestService.handle("weekly sales review",3)
        self.assertIn("permission",result["message"].lower())


if __name__=="__main__":unittest.main()
