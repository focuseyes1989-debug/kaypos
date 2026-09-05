"""Read-only Native assistant using shared Burmese/English intent parsers.

Only audited server repositories execute queries. Free text never becomes SQL,
an external message, a listener, a settings mutation or a background schedule.
"""
from datetime import date, timedelta
import re

from server.native_admin import AdminRepository
from server.native_reports import ReportRepository, VIEWS
from native_pos.assistant_queries import REPORT_CHOICES
from native_pos.sales_digest import digest_period, digest_message
from native_pos.routes import ROUTES
from native_pos.admin_schema import EMPLOYEE_SECTIONS
from ui.ai_pages.ai_burmese_normalizer import AIBurmeseNormalizer
from ui.ai_pages.ai_nlp_processor import NLProcessor
from ui.ai_pages.ai_navigation import AINavigationRequest


class AssistantRepository(AdminRepository):
    def ask(self, user, query):
        if not query.strip() or len(query) > 1000: raise ValueError('Enter a question of 1 to 1,000 characters')
        conn = self.connect()
        try: self.authorize(conn.cursor(), user, ['ai_pages'])
        finally: conn.rollback(); conn.close()
        period = digest_period(query)
        if period:
            result = self.report_answer(user, 'summary', 'overview', *period)
            result['message'] = digest_message(result['report'])
            result['digest'] = True
            return result
        query = AIBurmeseNormalizer.normalize(query); navigation = AINavigationRequest.parse(query)
        explicit = re.fullmatch(r'report\s+(summary|reports)/([a-z]+)(?:\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2}))?', query.strip(), re.I)
        if explicit:
            section, view, start, end = explicit.groups(); section = section.lower(); view = view.lower()
            if view not in VIEWS[section]: raise ValueError('Unsupported report view')
            return self.report_answer(user, section, view, start or date.today().isoformat(), end or date.today().isoformat())
        if query.casefold().startswith('report '):
            raise ValueError('Use report summary/hourly YYYY-MM-DD YYYY-MM-DD, or choose a report in the assistant.')
        # Anchored phrases take priority over generic "today sales" patterns.
        for label, section, view in REPORT_CHOICES:
            match = re.fullmatch(re.escape(label) + r'(?:\s+(today|yesterday|this month))?(?:\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{4}-\d{2}-\d{2}))?)?', query.strip(), re.I)
            if match:
                period, start, end = match.groups(); today = date.today()
                first = today.replace(day=1) if period and period.lower() == 'this month' else today - timedelta(days=1) if period and period.lower() == 'yesterday' else today
                last = today if period and period.lower() == 'this month' else first
                return self.report_answer(user, section, view, start or first.isoformat(), end or start or last.isoformat())
        if navigation:
            route = next((r for r in ROUTES if r.permission == navigation['page']), None)
            if route:
                permission = route.permission
                tab = {'finance': 'advances', 'cash_sessions': 'cash'}.get(navigation.get('tab'), navigation.get('tab'))
                required = [permission]
                if tab in EMPLOYEE_SECTIONS: required.append(EMPLOYEE_SECTIONS[tab][1])
                conn = self.connect()
                try: self.authorize(conn.cursor(), user, required)
                finally: conn.rollback(); conn.close()
                return dict(message='Open ' + route.title, route_id=route.id, tab=tab, filters=navigation.get('filters', {}), records=[])
        plan = NLProcessor.detect_intent(query); intent = plan['intent']; today = date.today()
        start = end = today
        if intent == 'sales_yesterday': start = end = today - timedelta(days=1)
        elif intent == 'sales_weekly': start = today - timedelta(days=6)
        elif 'monthly' in intent: start = today.replace(day=1)
        dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', query)
        if dates: start = date.fromisoformat(dates[0]); end = date.fromisoformat(dates[-1])
        mapping = {
            'sales_today': ('summary', 'overview'), 'sales_yesterday': ('summary', 'overview'),
            'sales_weekly': ('summary', 'daily'), 'sales_monthly': ('summary', 'daily'),
            'top_products': ('summary', 'items'), 'stock_summary': ('reports', 'inventory'),
            'low_stock': ('reports', 'inventory'), 'expenses_today': ('reports', 'expenses'),
            'expenses_monthly': ('reports', 'expenses'), 'profit': ('reports', 'financial'),
            'debt_summary': ('reports', 'credit'),
        }
        if intent in mapping:
            section, view = mapping[intent]
            result = self.report_answer(user, section, view, start.isoformat(), end.isoformat())
            report = result['report']
            if intent == 'low_stock':
                report['tables'][0]['rows'] = [r for r in report['tables'][0]['rows'] if r['status'] in ('Low stock', 'Out of stock')]
                report['tables'][0]['title'] = 'Low / out of stock'
            return result
        if intent in ('product_detail', 'product_search'):
            identifier = plan.get('entities', {}).get('identifier') or plan.get('entities', {}).get('search_term')
            identifier = str(identifier or query).strip()
            conn = self.connect(); c = conn.cursor()
            try:
                self.authorize(c, user, ['products'])
                records = self.rows(c, '''SELECT id,name,sku,barcode,price,sold_by FROM products
                    WHERE LOWER(name) LIKE ? OR sku=? OR barcode=? ORDER BY name LIMIT 100''',
                    ('%' + identifier.lower() + '%', identifier, identifier))
                return dict(message='Matching products (maximum 100). Open Products for stock and variant details.', records=records, route_id=2)
            finally: conn.rollback(); conn.close()
        return dict(message='Native assistant supports: today sales, yesterday sales, weekly sales, monthly sales, top products, stock summary, expense today/monthly, profit, debt summary, product name/barcode, and "open attendance/payroll/products".\nUse the report selector for all 17 Native summary/report views, or ask "hourly sales", "payment types", "stock movements" or "report summary/hourly YYYY-MM-DD YYYY-MM-DD".\nAdd YYYY-MM-DD or a pair of dates for a report period. Use Error diagnostics for local pasted-error guidance. Scheduled digests remain in the original KAY POS AI.', records=[])

    def report_answer(self, user, section, view, start, end):
        report = ReportRepository(self.service).read(user, section, view, start, end)
        return dict(message=f'{view.title()} · {start} to {end}\n' + '\n'.join(report.get('notes', [])),
                    report=report, report_section=section, route_id=1 if section == 'summary' else 12, records=[])


def install_routes(app, current_user, repository=None):
    from fastapi import Depends, HTTPException
    from pydantic import BaseModel, Field
    repo = repository or AssistantRepository()
    class Question(BaseModel):
        query: str = Field(min_length=1, max_length=1000)
    @app.post('/api/native/assistant')
    def ask(payload: Question, user=Depends(current_user)):
        try: return repo.ask(user, payload.query)
        except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
        except ValueError as exc: raise HTTPException(400, str(exc)) from exc
