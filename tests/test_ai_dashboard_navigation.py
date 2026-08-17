import unittest

from ui.ai_pages.ai_chat_room import AIChatRoom
from ui.main_window.main_window_ui import MainWindowUI


class _ActionBuilder:
    @staticmethod
    def _navigation_callback(request):
        return request


class _DateRange:
    def __init__(self):self.value=None
    def set_range(self,start,end):self.value=(start,end)


class _Tabs:
    def __init__(self,count=7):self.index=0;self._count=count
    def count(self):return self._count
    def setCurrentIndex(self,index):self.index=index
    def isTabEnabled(self,index):return True


class _Page:
    def __init__(self):
        self.date_range=_DateRange();self.tabs=_Tabs();self.tab_widget=_Tabs(4);self.loads=0
    def load_all_tabs(self):self.loads+=1
    def load_expenses(self):self.loads+=1
    def update_cards(self):self.loads+=1
    def refresh_all(self):self.loads+=1


class TestAIDashboardNavigation(unittest.TestCase):
    def test_summary_drill_down_is_permission_safe_and_limited(self):
        result={"type":"dashboard_summary","start_date":"2026-08-01","end_date":"2026-08-17","metrics":{
            "attendance_issues":4,"open_cash_sessions":1,"low_stock":2,"out_of_stock":1,
            "outstanding_credit":500,"refunds":10,"discounts":5,
        }}
        actions=AIChatRoom._dashboard_navigation_actions(_ActionBuilder(),result,{"dashboard","attendance","inventory","sales_summary"})
        self.assertLessEqual(len(actions),3)
        labels=[label for label,_request in actions]
        self.assertIn("Open Attendance",labels)
        self.assertIn("Open Low Stock",labels)
        self.assertNotIn("Open Credit Customers",labels)
        attendance=next(request for label,request in actions if label=="Open Attendance")
        self.assertEqual(attendance["page"],"employees")
        self.assertEqual(attendance["filters"]["start_date"],"2026-08-01")

    def test_chart_routes_to_matching_sales_summary_tab(self):
        result={"type":"dashboard_chart","chart_kind":"payments","start_date":"2026-08-01","end_date":"2026-08-17"}
        actions=AIChatRoom._dashboard_navigation_actions(_ActionBuilder(),result,{"dashboard","sales_summary"})
        self.assertEqual(actions[0][0],"Open Payments")
        self.assertEqual(actions[0][1]["filters"]["tab"],"payments")

    def test_personal_results_never_link_to_company_reports(self):
        result={"type":"dashboard_alerts","scope":"personal","start_date":"2026-08-01","end_date":"2026-08-17","data":[
            {"Title":"High refund rate","Target":"receipts","Tab":"refunds"},
            {"Title":"Attendance issues","Target":"employees","Tab":"attendance"},
        ]}
        permissions={"sales","receipts","attendance","sales_summary","expense"}
        actions=AIChatRoom._dashboard_navigation_actions(_ActionBuilder(),result,permissions)
        self.assertEqual([label for label,_ in actions],["Open Sales"])
        self.assertEqual(actions[0][1]["page"],"sales")

    def test_alert_drill_down_uses_alert_target_and_employee_tab(self):
        result={"type":"dashboard_alerts","start_date":"2026-08-01","end_date":"2026-08-17","data":[
            {"Title":"Open cash sessions","Target":"employees","Tab":"cash_sessions"},
            {"Title":"Out of stock","Target":"inventory","Tab":"low_stock"},
        ]}
        actions=AIChatRoom._dashboard_navigation_actions(_ActionBuilder(),result,{"dashboard","cash_sessions","inventory"})
        self.assertEqual(actions[0][1]["tab"],"cash_sessions")
        self.assertEqual(actions[1][1]["filters"]["tab"],"low_stock")

    def test_explanation_routes_to_authorized_breakdowns(self):
        result={"type":"dashboard_explanation","explanation_focus":"profit","start_date":"2026-08-01","end_date":"2026-08-17"}
        actions=AIChatRoom._dashboard_navigation_actions(_ActionBuilder(),result,{"dashboard","sales_summary","expense"})
        self.assertEqual([label for label,_ in actions],["Open Sales Breakdown","Open Expense Breakdown"])

    def test_common_adapter_applies_date_and_sales_tab(self):
        page=_Page()
        MainWindowUI._apply_ai_page_filters(page,"sales_summary",{"start_date":"2026-08-01","end_date":"2026-08-17","tab":"payments"})
        self.assertEqual(page.date_range.value,("2026-08-01","2026-08-17"))
        self.assertEqual(page.tabs.index,6)
        self.assertEqual(page.loads,1)

    def test_common_adapter_selects_inventory_and_receipt_tabs(self):
        inventory=_Page();MainWindowUI._apply_ai_page_filters(inventory,"inventory",{"tab":"low_stock"})
        receipts=_Page();MainWindowUI._apply_ai_page_filters(receipts,"receipts",{"tab":"refunds"})
        self.assertEqual(inventory.tabs.index,1)
        self.assertEqual(receipts.tab_widget.index,1)
        self.assertEqual(inventory.loads,1)
        self.assertEqual(receipts.loads,1)


if __name__=="__main__":unittest.main()
