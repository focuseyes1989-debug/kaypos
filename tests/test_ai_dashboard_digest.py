import unittest
from datetime import date
from unittest.mock import patch

from ui.ai_pages.ai_dashboard_digest import DashboardDigestScheduler,DashboardDigestService


class TestAIDashboardDigest(unittest.TestCase):
    def test_digest_intents_and_current_periods(self):
        self.assertTrue(DashboardDigestService.handles("weekly business review"))
        self.assertTrue(DashboardDigestService.handles("လစဉ်အစီရင်ခံစာ"))
        self.assertEqual(DashboardDigestService.current_period("weekly",date(2026,8,17)),("2026-08-17","2026-08-17"))
        self.assertEqual(DashboardDigestService.current_period("monthly",date(2026,8,17)),("2026-08-01","2026-08-17"))

    def test_digest_requires_dashboard_permission(self):
        with patch.object(DashboardDigestService,"_permissions",return_value={"sales"}):
            result=DashboardDigestService.handle("daily executive summary",1)
        self.assertIn("permission",result["message"].lower())

    def test_existing_digest_is_idempotently_reused(self):
        existing={"type":"dashboard_digest","message":"existing","data":[]}
        with patch.object(DashboardDigestService,"ensure_schema"),patch.object(DashboardDigestService,"_load",return_value=existing),patch("ui.ai_pages.ai_dashboard_digest.AIDashboardQueryHandler.collect") as collect:
            result=DashboardDigestService.generate("daily","2026-08-16","2026-08-16",1,{"dashboard"})
        self.assertIs(result,existing);collect.assert_not_called()

    def test_scheduler_uses_latest_completed_periods_once_per_key(self):
        with patch.object(DashboardDigestScheduler,"enabled",return_value=True),patch.object(DashboardDigestService,"_permissions",return_value={"dashboard"}),patch.object(DashboardDigestService,"generate",side_effect=lambda kind,start,end,*args:{"kind":kind,"start":start,"end":end}) as generate:
            results=DashboardDigestScheduler.run_due(1,"Admin",date(2026,8,17))
        self.assertEqual(len(results),3)
        self.assertEqual(generate.call_args_list[0].args[:3],("daily","2026-08-16","2026-08-16"))
        self.assertEqual(generate.call_args_list[1].args[:3],("weekly","2026-08-10","2026-08-16"))
        self.assertEqual(generate.call_args_list[2].args[:3],("monthly","2026-07-01","2026-07-31"))

    def test_disabled_scheduler_does_nothing(self):
        with patch.object(DashboardDigestScheduler,"enabled",return_value=False),patch.object(DashboardDigestService,"generate") as generate:
            self.assertEqual(DashboardDigestScheduler.run_due(1,"Admin",date(2026,8,17)),[])
        generate.assert_not_called()

    def test_digest_message_states_local_delivery(self):
        metrics={"net_sales":100,"transactions":2,"gross_profit":40,"expenses":10,"net_profit":30}
        message=DashboardDigestService._message("daily","2026-08-17","2026-08-17","2026-08-16","2026-08-16",metrics,{},[])
        self.assertIn("stored locally",message)
        self.assertIn("No email, Telegram",message)

    def test_stored_digest_is_filtered_for_current_reader(self):
        payload={"metrics":{"net_sales":100,"outstanding_credit":500,"attendance_issues":2,"open_cash_sessions":1},"previous_metrics":{},"changes":{"attendance_issues":{}},"alerts":[
            {"Target":"customers","Tab":"outstanding"},{"Target":"employees","Tab":"attendance"},{"Target":"inventory","Tab":"low_stock"}],
        }
        filtered=DashboardDigestService._filter_payload(payload,{"dashboard","inventory"})
        self.assertNotIn("outstanding_credit",filtered["metrics"])
        self.assertNotIn("attendance_issues",filtered["metrics"])
        self.assertNotIn("open_cash_sessions",filtered["metrics"])
        self.assertEqual(len(filtered["alerts"]),1)


if __name__=="__main__":unittest.main()
