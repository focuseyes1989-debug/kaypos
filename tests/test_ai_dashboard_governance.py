import unittest
from unittest.mock import patch

from ui.ai_pages.ai_dashboard_governance import DashboardAIGovernance


class _Cursor:
    def __init__(self,rows=()):self.rows=list(rows);self.executions=[]
    def execute(self,sql,params=()):self.executions.append((sql,params));return self
    def fetchall(self):return self.rows


class _Connection:
    def __init__(self,rows=()):self.value=_Cursor(rows);self.committed=False;self.closed=False
    def cursor(self):return self.value
    def commit(self):self.committed=True
    def close(self):self.closed=True


class TestDashboardAIGovernance(unittest.TestCase):
    def test_enrichment_adds_scope_sources_and_timestamp(self):
        result={"type":"dashboard_summary","message":"Summary","scope":"personal","start_date":"2026-08-01","end_date":"2026-08-17","metrics":{"net_sales":10,"expenses":None,"attendance_issues":2}}
        enriched=DashboardAIGovernance.enrich(result)
        self.assertEqual(enriched["provenance"]["scope"],"personal")
        self.assertIn("attendance",enriched["provenance"]["sources"])
        self.assertNotIn("expenses",enriched["provenance"]["sources"])
        self.assertIn("Data scope: personal",enriched["message"])

    def test_record_stores_metadata_without_result_rows(self):
        schema=_Connection();insert=_Connection()
        result={"type":"dashboard_chart","scope":"personal","start_date":"2026-08-01","end_date":"2026-08-17","data":[{"sensitive":"not stored"}]}
        DashboardAIGovernance.enrich(result)
        with patch("ui.ai_pages.ai_dashboard_governance.connect_db",side_effect=[schema,insert]):
            DashboardAIGovernance.record("my dashboard chart",8,result,.125,True)
        _sql,params=insert.value.executions[0]
        self.assertEqual(params[0],8);self.assertEqual(params[3],"personal");self.assertEqual(params[-1],125)
        self.assertNotIn("sensitive",str(params))

    def test_audit_history_requires_dashboard_permission(self):
        with patch("ui.ai_pages.ai_dashboard_governance.PermissionManager.get_user_permissions",return_value={"sales"}),patch.object(DashboardAIGovernance,"_role",return_value="cashier"):
            result=DashboardAIGovernance.handle("dashboard AI audit history",8)
        self.assertIn("permission",result["message"].lower())

    def test_authorized_audit_history_is_readable(self):
        schema=_Connection();read=_Connection([("2026-08-17 12:00",1,"dashboard_summary","business","2026-08-17","2026-08-17",25,1)])
        with patch("ui.ai_pages.ai_dashboard_governance.PermissionManager.get_user_permissions",return_value={"dashboard"}),patch.object(DashboardAIGovernance,"_role",return_value="manager"),patch("ui.ai_pages.ai_dashboard_governance.connect_db",side_effect=[schema,read]):
            result=DashboardAIGovernance.handle("dashboard စစ်ဆေးမှတ်တမ်း ပြပါ",1)
        self.assertEqual(result["type"],"dashboard_audit");self.assertEqual(result["data"][0]["Scope"],"business")


if __name__=="__main__":unittest.main()
