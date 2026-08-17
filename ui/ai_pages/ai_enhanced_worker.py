# ui/ai_pages/ai_enhanced_worker.py
"""
Enhanced query worker with NLP and analytics
"""

from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
from loguru import logger
import re

from ui.ai_pages.ai_nlp_processor import NLProcessor
from ui.ai_pages.ai_bilingual_terms import QueryLexicon
from ui.ai_pages.ai_query_handlers import QueryHandlers
from ui.ai_pages.ai_response_templates import ResponseTemplates
from ui.ai_pages.ai_analytics import AIAnalytics
from ui.ai_pages.ai_cache import _query_cache

# 🆕 New imports
from ui.ai_pages.ai_product_search import AIProductSearch
from ui.ai_pages.ai_troubleshooter import AITroubleshooter
from ui.ai_pages.ai_settings_assistant import AISettingsAssistant
from ui.ai_pages.ai_employee_queries import EmployeeQueryHandler
from ui.ai_pages.ai_usage_guide import ProjectUsageGuide
from ui.ai_pages.ai_error_diagnostics import AIErrorDiagnostics
from ui.ai_pages.ai_natural_language import AINaturalLanguagePlanner, AIInsightHandler
from ui.ai_pages.ai_burmese_normalizer import AIBurmeseNormalizer


class EnhancedQueryWorker(QThread):
    """Enhanced background thread with NLP and analytics"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, query: str, user_id: str = None):
        super().__init__()
        self.query = AIBurmeseNormalizer.normalize(query)
        self.user_id = user_id
        self._is_running = True
        
        # Initialize components
        self.nlp = NLProcessor()
        self.analytics = AIAnalytics()
        
        # Set cache for query handlers
        QueryHandlers.set_cache(_query_cache)
    
    def stop(self):
        self._is_running = False
    
    def run(self):
        start_time = datetime.now()
        success = True
        result = None
        intent_result = {'intent': 'unknown', 'entities': {}}
        is_debt_query = False
        is_new_intent = False
        result_emitted = False
        
        try:
            self.progress.emit(10)

            diagnostic_result = AIErrorDiagnostics.handle(self.query)
            if diagnostic_result is not None:
                self.progress.emit(100)
                result = diagnostic_result
                intent_result = {'intent': 'diagnostic', 'entities': {}}
                return

            usage_result = ProjectUsageGuide.handle(self.query)
            if usage_result is not None:
                self.progress.emit(100)
                result = usage_result
                intent_result = {'intent': 'usage_guide', 'entities': {}}
                return

            insight_plan=AINaturalLanguagePlanner.plan(self.query)
            if insight_plan is not None:
                self.progress.emit(40)
                result=AIInsightHandler.handle(insight_plan,self.query,self.user_id)
                self.progress.emit(100)
                intent_result={'intent': insight_plan.get('intent','insight'), 'entities': {}}
                return

            project_result = self._check_project_query()
            if project_result is not None:
                self.progress.emit(100)
                result = project_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'project_help'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            employee_result = EmployeeQueryHandler.handle(self.query, self.user_id)
            if employee_result is not None:
                self.progress.emit(100)
                result = employee_result
                intent_result = {'intent': 'employee_query', 'entities': {}}
                return

            receipts_result = self._check_receipts_query()
            if receipts_result is not None:
                self.progress.emit(100)
                result = receipts_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'receipts'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            sales_summary_result = self._check_sales_summary_query()
            if sales_summary_result is not None:
                self.progress.emit(100)
                result = sales_summary_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'sales_summary'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            date_result = self._check_date_query()
            if date_result is not None:
                self.progress.emit(100)
                result = date_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'date_query'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            expense_result = self._check_expense_query()
            if expense_result is not None:
                self.progress.emit(100)
                result = expense_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'expense_query'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            customer_result = self._check_customer_query()
            if customer_result is not None:
                self.progress.emit(100)
                result = customer_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'customer_query'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return
            
            # 🔥 FIRST: Check for debt queries directly (before NLP)
            debt_result = self._check_debt_query()
            if debt_result is not None:
                self.progress.emit(100)
                result = debt_result
                success = True
                is_debt_query = True
                # Log analytics
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    'debt_summary',
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            product_result = self._check_product_inventory_query()
            if product_result is not None:
                self.progress.emit(100)
                result = product_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'product_query'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return

            profit_result = self._check_profit_query()
            if profit_result is not None:
                self.progress.emit(100)
                result = profit_result
                success = True
                response_time = (datetime.now() - start_time).total_seconds()
                self.analytics.log_query(
                    self.query,
                    result.get('type', 'profit'),
                    True,
                    response_time,
                    self.user_id
                )
                self.finished.emit(result)
                result_emitted = True
                return
            
            # Detect intent
            intent_result = self.nlp.detect_intent(self.query)
            self.progress.emit(30)
            
            # 🆕 Check for new intents (product_search, add_to_cart, etc.)
            intent = intent_result.get('intent', 'unknown')
            if intent in ['product_search', 'add_to_cart', 'check_stock', 'troubleshoot', 'settings']:
                is_new_intent = True
                result = self._route_new_intent(intent, intent_result)
                if result:
                    self.progress.emit(100)
                    # Log analytics
                    response_time = (datetime.now() - start_time).total_seconds()
                    self.analytics.log_query(
                        self.query,
                        intent,
                        True,
                        response_time,
                        self.user_id
                    )
                    self.finished.emit(result)
                    result_emitted = True
                    return
            
            # Route to appropriate handler (existing intents)
            result = self._route_by_intent(intent_result)
            self.progress.emit(80)
            
            # 🔥 ONLY enhance response if NOT a debt query and NOT a new intent
            if result and result.get('type') != 'error' and not is_debt_query and not is_new_intent:
                result = self._enhance_response(result, intent_result)
            
            self.progress.emit(100)
            
        except Exception as e:
            success = False
            diagnostic=AIErrorDiagnostics.diagnose(str(e))
            result = {
                'type': 'diagnostic',
                'data': [],
                'message': AIErrorDiagnostics.format(diagnostic),
                'sql': '',
                'diagnostic': diagnostic,
            }
            logger.error(f"Query error: {AIErrorDiagnostics.redact(e)}")
        
        finally:
            # Make sure result is not None before emitting
            if result is None:
                # Create fallback response
                is_myanmar = self.nlp.is_myanmar_query(self.query)
                if is_myanmar:
                    message = "❌ နားမလည်ပါ။ ကျေးဇူးပြု၍ အောက်ပါမေးခွန်းများကို မေးမြန်းပါ:\n\n" + QueryHandlers.get_help_text_myanmar()
                else:
                    message = "❌ I don't understand. Please ask one of these questions:\n\n" + QueryHandlers.get_help_text()
                
                result = {
                    'type': 'response',
                    'data': [],
                    'message': message,
                    'sql': ''
                }
            
            # Log analytics (skip if already logged for debt query or new intent)
            if not is_debt_query and not is_new_intent:
                response_time = (datetime.now() - start_time).total_seconds()
                logged_query=AIErrorDiagnostics.redact(self.query) if result.get('type')=='diagnostic' else self.query
                self.analytics.log_query(
                    logged_query,
                    intent_result.get('intent', 'unknown'),
                    success,
                    response_time,
                    self.user_id
                )
            
            if not result_emitted:
                self.finished.emit(result)

    def _check_project_query(self):
        """Show bilingual coverage/help for the whole POS project."""
        query_lower = self.query.lower().strip()
        asks_for_help = QueryLexicon.has_any(query_lower, "help")
        asks_for_project = QueryLexicon.has_any(query_lower, "project")
        if not asks_for_help and not asks_for_project:
            return None

        if asks_for_help or asks_for_project:
            language_note = "English/Myanmar"
            message = (
                f"🤖 ZAY POS AI Assistant ({language_note})\n\n"
                "You can ask about these project areas in English or Myanmar:\n\n"
                "• Sales: today/yesterday/monthly/total sales, daily summaries\n"
                "• Sales Summary: top items, categories, payment types, category groups\n"
                "• Receipts: receipt summary, recent receipts, invoice detail, refunds, discounts, credit receipts\n"
                "• Products & Inventory: product search, barcode/SKU details, stock summary, low stock\n"
                "• Customers: search customer, customer profile, top customers, customer statistics\n"
                "• Credit/Debt: debt summary, customer debt, overdue debts, recent debts\n"
                "• Expenses: today/monthly/total expenses, recent expenses, category expenses\n"
                "• Profit: profit summary\n"
                "• Employees: profiles, attendance issues, shifts, leave, payroll, advances, performance, cash sessions\n\n"
                "Examples:\n"
                "• today sales / ယနေ့ ရောင်းအား\n"
                "• sales by category 31.7.2026 / 31.7.2026 အရောင်း အမျိုးအစား\n"
                "• receipt INV20260731111700 / ပြေစာ INV20260731111700\n"
                "• low stock / စတော့နည်း\n"
                "• expense category ဈေးဖိုး / ဈေးဖိုး ဒီနေ့\n"
                "• customer Mg Mg / ဖောက်သည် Mg Mg\n"
                "• today employee attendance / ဒီနေ့ ဝန်ထမ်း attendance\n"
                "• EMP-0008 shift / pending employee leave\n"
            )
            return {
                'type': 'project_help',
                'data': [],
                'message': message,
                'sql': ''
            }

        return None

    def _check_receipts_query(self):
        """Route Receipts page style questions."""
        query_lower = self.query.lower().strip()
        has_receipt_pattern = QueryLexicon.has_any(query_lower, "receipt")
        if not has_receipt_pattern:
            return None

        from_date, to_date, label = self._parse_receipts_range()
        view = self._detect_receipts_view(query_lower)
        search_term = self._extract_receipt_search_term(view)
        limit = self._extract_limit(default=10)
        return QueryHandlers.get_receipts_report(
            from_date,
            to_date,
            label,
            view=view,
            search_term=search_term,
            limit=limit
        )

    def _parse_receipts_range(self):
        return self._parse_sales_summary_range()

    def _detect_receipts_view(self, query_lower):
        if QueryLexicon.has_any(query_lower, "summary"):
            return "overview"
        if QueryLexicon.has_any(query_lower, "refund"):
            return "refund"
        if QueryLexicon.has_any(query_lower, "discount"):
            return "discount"
        if QueryLexicon.has_any(query_lower, "debt"):
            return "credit"
        if QueryLexicon.has_any(query_lower, "list"):
            return "receipts"

        search_term = self._extract_receipt_search_term("detail")
        has_detail_word = any(word in query_lower for word in ['detail', 'details', 'invoice', 'voucher'])
        has_singular_receipt = bool(re.search(r'\breceipt\b', query_lower))
        has_invoice_number = bool(re.search(r'\b(?:inv|invoice)[\w-]*\d|\d{5,}', search_term, re.IGNORECASE))
        if search_term and (has_detail_word or has_singular_receipt or has_invoice_number):
            return "detail"

        return "overview"

    def _extract_receipt_search_term(self, view):
        if view != "detail":
            return ""

        term = self._strip_date_expression(self.query)
        remove_words = ['detail', 'details', 'no', 'number', '#']
        remove_words.extend(QueryLexicon.words("receipt", "list", "refund", "discount", "summary"))
        for word in sorted(remove_words, key=len, reverse=True):
            term = re.sub(rf'\b{re.escape(word)}\b', ' ', term, flags=re.IGNORECASE)
            term = term.replace(word, " ")
        return " ".join(term.split())

    def _check_product_inventory_query(self):
        """Route bilingual product and inventory questions before broad NLP search."""
        query_lower = self.query.lower().strip()
        has_product = QueryLexicon.has_any(query_lower, "product")
        has_stock = QueryLexicon.has_any(query_lower, "stock")

        if QueryLexicon.has_any(query_lower, "low") and has_stock:
            return QueryHandlers.get_low_stock_products()

        if has_stock and QueryLexicon.has_any(query_lower, "summary"):
            return QueryHandlers.get_stock_summary()

        if QueryLexicon.has_any(query_lower, "top") and (has_product or QueryLexicon.has_any(query_lower, "sales")):
            limit = self._extract_limit(default=5)
            return QueryHandlers.get_top_products(limit)

        if not has_product and not has_stock:
            return None

        if has_stock and not QueryLexicon.has_any(query_lower, "list"):
            product_name = QueryLexicon.remove_terms(
                self.query,
                "stock", "product", "list",
                extra=["how many", "available", "qty", "quantity"]
            )
            if product_name:
                results = AIProductSearch.search(product_name, limit=1)
                if results:
                    p = results[0]
                    return {
                        'type': 'check_stock',
                        'data': [p],
                        'message': (
                            f"📦 **{p['name']}**\n"
                            f"• Stock: {p['stock']} units\n"
                            f"• Price: {p['price']} Ks\n"
                            f"• Category: {p['category']}"
                        ),
                        'sql': ''
                    }
            return QueryHandlers.get_stock_summary()

        search_term = QueryLexicon.remove_terms(self.query, "product", "list", extra=["detail", "details"])
        if search_term:
            results = AIProductSearch.search(search_term)
            return self._format_product_search_results(results, search_term)

        return QueryHandlers.get_stock_summary()

    def _check_profit_query(self):
        query_lower = self.query.lower().strip()
        if QueryLexicon.has_any(query_lower, "profit"):
            return QueryHandlers.get_profit_summary()
        return None
    
    def _check_sales_summary_query(self):
        """Route Sales Summary page style questions."""
        query_lower = self.query.lower().strip()
        if (
            QueryLexicon.has_any(query_lower, "sales_summary")
            or (
                QueryLexicon.has_any(query_lower, "sales")
                and (
                    QueryLexicon.has_any(query_lower, "summary")
                    or QueryLexicon.has_any(query_lower, "category", "payment")
                )
            )
            or (
                QueryLexicon.has_any(query_lower, "top")
                and QueryLexicon.has_any(query_lower, "sales")
                and QueryLexicon.has_any(query_lower, "product")
            )
        ):
            from_date, to_date, label = self._parse_sales_summary_range()
            view = self._detect_sales_summary_view(query_lower)
            limit = self._extract_limit(default=10)
            return QueryHandlers.get_sales_summary_report(from_date, to_date, label, view=view, limit=limit)
        summary_words = [
            'sales summary', 'sale summary', 'summary sales',
            'sales by item', 'sales by category', 'sales by payment',
            'sales by parent', 'sales by group', 'top sales items',
            'top items sales', 'ရောင်းအားစုစည်း', 'ရောင်းအား အကျဉ်းချုပ်',
            'ရောင်းအားစာရင်း', 'အရောင်းစာရင်းချုပ်'
        ]

        has_sales_summary_pattern = any(word in query_lower for word in summary_words)
        has_top_sales_items = (
            'top' in query_lower
            and any(word in query_lower for word in ['sales', 'sale', 'ရောင်းအား'])
            and any(word in query_lower for word in ['item', 'items', 'product', 'products', 'ပစ္စည်း'])
        )
        if not has_sales_summary_pattern and not has_top_sales_items:
            return None

        from_date, to_date, label = self._parse_sales_summary_range()
        view = self._detect_sales_summary_view(query_lower)
        limit = self._extract_limit(default=10)
        return QueryHandlers.get_sales_summary_report(from_date, to_date, label, view=view, limit=limit)

    def _parse_sales_summary_range(self):
        query_lower = self.query.lower().strip()
        today = datetime.now()

        if QueryLexicon.has_any(query_lower, "this_month"):
            start = today.replace(day=1)
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Month"

        if QueryLexicon.has_any(query_lower, "last_month"):
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start.strftime("%Y-%m-%d"), last_month_end.strftime("%Y-%m-%d"), "Last Month"

        if QueryLexicon.has_any(query_lower, "this_week"):
            start = today - timedelta(days=today.weekday())
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Week"

        if QueryLexicon.has_any(query_lower, "this_year"):
            start = today.replace(month=1, day=1)
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Year"

        if any(word in query_lower for word in ['this month', 'monthly', 'ဒီလ', 'လစဉ်']):
            start = today.replace(day=1)
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Month"

        if any(word in query_lower for word in ['last month', 'ပြီးခဲ့တဲ့လ']):
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start.strftime("%Y-%m-%d"), last_month_end.strftime("%Y-%m-%d"), "Last Month"

        if any(word in query_lower for word in ['this week', 'weekly', 'ဒီတစ်ပတ်', 'အပတ်စဉ်']):
            start = today - timedelta(days=today.weekday())
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Week"

        if any(word in query_lower for word in ['this year', 'yearly', 'ဒီနှစ်', 'နှစ်စဉ်']):
            start = today.replace(month=1, day=1)
            return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), "This Year"

        date_matches = re.findall(r'(?<!\d)(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}-\d{1,2}-\d{1,2})(?!\d)', self.query)
        if len(date_matches) >= 2:
            start, _ = QueryHandlers.parse_date_expression(date_matches[0])
            end, _ = QueryHandlers.parse_date_expression(date_matches[1])
            if start and end:
                return start, end, f"{start} to {end}"

        date_str, label = QueryHandlers.parse_date_expression(self.query)
        if date_str:
            return date_str, date_str, label

        today_str = today.strftime("%Y-%m-%d")
        return today_str, today_str, "Today"

    def _detect_sales_summary_view(self, query_lower):
        if QueryLexicon.has_any(query_lower, "payment"):
            return "payment"
        if "parent category" in query_lower or "\u1019\u102d\u1018" in query_lower:
            return "parent"
        if "category group" in query_lower or "\u1021\u102f\u1015\u103a\u1005\u102f" in query_lower:
            return "group"
        if QueryLexicon.has_any(query_lower, "category"):
            return "category"
        if QueryLexicon.has_any(query_lower, "product", "top"):
            return "top_items"

        if any(word in query_lower for word in ['payment', 'payments', 'payment type', 'ငွေပေး']):
            return "payment"
        if any(word in query_lower for word in ['parent category', 'parent', 'မိဘအမျိုးအစား']):
            return "parent"
        if any(word in query_lower for word in ['category group', 'group', 'အုပ်စု']):
            return "group"
        if any(word in query_lower for word in ['category', 'categories', 'အမျိုးအစား']):
            return "category"
        if any(word in query_lower for word in ['item', 'items', 'product', 'products', 'top', 'ပစ္စည်း']):
            return "top_items"
        return "overview"

    def _extract_limit(self, default=10):
        query_without_dates = re.sub(r'(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{4}(?!\d)', ' ', self.query)
        query_without_dates = re.sub(r'(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)', ' ', query_without_dates)
        match = re.search(r'(?:top|limit|first)\s+(\d+)', query_without_dates, re.IGNORECASE)
        if not match:
            match = re.search(r'(\d+)\s+(?:items|products|categories|payments|groups)', query_without_dates, re.IGNORECASE)
        return int(match.group(1)) if match else default

    def _check_date_query(self):
        """Route queries that include a date expression."""
        date_str, label = QueryHandlers.parse_date_expression(self.query)
        if not date_str:
            return None

        query_lower = self.query.lower().strip()
        expense_words = [
            'expense', 'expenses', 'cost', 'costs', 'spending',
            'အသုံးစရိတ်', 'ကုန်ကျ', 'အသုံး', 'သုံးစွဲ', 'စရိတ်'
        ]
        sales_words = ['sales', 'sale', 'revenue', 'ရောင်းအား', 'ရောင်း']
        category_term = self._strip_date_expression(self.query)
        matched_category = QueryHandlers.find_expense_category(self._clean_expense_term(category_term))

        if matched_category:
            return QueryHandlers.get_expenses_by_category_and_date(matched_category, date_str, label)

        if QueryLexicon.has_any(query_lower, "expense"):
            return QueryHandlers.get_expenses_by_date(date_str, label)

        if QueryLexicon.has_any(query_lower, "sales"):
            return QueryHandlers.get_sales_by_date(date_str, label)

        if any(word in query_lower for word in expense_words):
            return QueryHandlers.get_expenses_by_date(date_str, label)

        if any(word in query_lower for word in sales_words):
            return QueryHandlers.get_sales_by_date(date_str, label)

        return QueryHandlers.get_daily_summary(date_str, label)

    def _strip_date_expression(self, text):
        stripped = text or ""
        date_words = [
            'day before yesterday', 'yesterday', 'today',
            'မနေ့တစ်နေ့က', 'တစ်နေ့က', 'မနေ့က', 'ယနေ့', 'ဒီနေ့'
        ]
        date_words.extend(QueryLexicon.words("day_before_yesterday", "yesterday", "today"))
        for word in date_words:
            stripped = stripped.replace(word, " ")
        stripped = re.sub(r'(?<!\d)\d{1,2}[./-]\d{1,2}[./-]\d{4}(?!\d)', ' ', stripped)
        stripped = re.sub(r'(?<!\d)\d{4}-\d{1,2}-\d{1,2}(?!\d)', ' ', stripped)
        return " ".join(stripped.split())

    def _check_expense_query(self):
        """Route expense queries before broad product search patterns."""
        query_lower = self.query.lower().strip()
        expense_words = [
            'expense', 'expenses', 'cost', 'costs', 'spending', 'spent',
            'အသုံးစရိတ်', 'ကုန်ကျ', 'အသုံး', 'သုံးစွဲ', 'စရိတ်'
        ]
        customer_words = ['customer', 'customers', 'ဝယ်သူ', 'ဝယ်ယူသူ', 'ဖောက်သည်']

        if any(word in query_lower for word in customer_words):
            return None

        list_category_phrases = [
            'expense categories', 'expenses categories', 'expense category list',
            'category list', 'categories list', 'all expense categories',
            'အသုံးစရိတ် အမျိုးအစား', 'အသုံးစရိတ်အမျိုးအစား', 'ကုန်ကျစရိတ် အမျိုးအစား',
            'အမျိုးအစား စာရင်း', 'ကဏ္ဍ စာရင်း'
        ]
        if any(phrase in query_lower for phrase in list_category_phrases):
            return QueryHandlers.get_expense_categories()

        matched_category = QueryHandlers.find_expense_category(self._clean_expense_term(self.query))
        if matched_category:
            return QueryHandlers.get_expenses_by_category(matched_category)

        if QueryLexicon.has_any(query_lower, "expense"):
            if QueryLexicon.has_any(query_lower, "category", "list"):
                return QueryHandlers.get_expense_categories()
            if QueryLexicon.has_any(query_lower, "today"):
                return QueryHandlers.get_today_expenses()
            if QueryLexicon.has_any(query_lower, "this_month"):
                return QueryHandlers.get_monthly_expenses()
            if QueryLexicon.has_any(query_lower, "list"):
                match = re.search(r'(\d+)', query_lower)
                limit = int(match.group(1)) if match else 10
                return QueryHandlers.get_recent_expenses(limit)
            if QueryLexicon.has_any(query_lower, "summary"):
                return QueryHandlers.get_total_expenses()
            return QueryHandlers.get_total_expenses()

        if not any(word in query_lower for word in expense_words):
            return None

        if any(word in query_lower for word in ['today', 'ယနေ့', 'ဒီနေ့']):
            return QueryHandlers.get_today_expenses()

        if any(word in query_lower for word in ['month', 'monthly', 'ဒီလ', 'လစဉ်']):
            return QueryHandlers.get_monthly_expenses()

        if any(word in query_lower for word in ['recent', 'latest', 'last', 'နောက်ဆုံး', 'မကြာသေး']):
            match = re.search(r'(\d+)', query_lower)
            limit = int(match.group(1)) if match else 10
            return QueryHandlers.get_recent_expenses(limit)

        category_patterns = [
            r'(?:expense|expenses|cost|costs)\s+(?:category|for|by)\s+["\']?([^"\']+)["\']?',
            r'(?:category)\s+(?:expense|expenses|cost|costs)\s+["\']?([^"\']+)["\']?',
            r'(?:အသုံးစရိတ်|ကုန်ကျ|စရိတ်).*(?:အမျိုးအစား|ကဏ္ဍ)\s*["\']?([^"\']+)["\']?',
            r'(?:အမျိုးအစား|ကဏ္ဍ).*(?:အသုံးစရိတ်|ကုန်ကျ|စရိတ်)\s*["\']?([^"\']+)["\']?',
        ]
        for pattern in category_patterns:
            match = re.search(pattern, self.query, re.IGNORECASE)
            if match:
                return QueryHandlers.get_expenses_by_category(self._clean_expense_term(match.group(1)))

        if any(word in query_lower for word in ['total', 'all', 'summary', 'စုစုပေါင်း', 'အားလုံး', 'စာရင်း']):
            return QueryHandlers.get_total_expenses()

        return QueryHandlers.get_total_expenses()

    def _clean_expense_term(self, term):
        term = (term or "").strip().strip('"\'')
        removable = [
            'expense', 'expenses', 'cost', 'costs', 'category', 'for', 'by',
            'show', 'find', 'check', 'summary', 'list',
            'စစ်', 'ကြည့်', 'ရှာ', 'စာရင်း',
            'အသုံးစရိတ်', 'ကုန်ကျ', 'စရိတ်', 'အမျိုးအစား', 'ကဏ္ဍ'
        ]
        removable.extend(QueryLexicon.words("expense", "category", "list", "summary"))
        for word in removable:
            term = re.sub(rf'\b{re.escape(word)}\b', '', term, flags=re.IGNORECASE).strip()
            term = term.replace(word, '').strip()
        return term

    def _check_customer_query(self):
        """Route customer queries before broad product search patterns."""
        query_lower = self.query.lower().strip()
        if QueryLexicon.has_any(query_lower, "customer"):
            if QueryLexicon.has_any(query_lower, "top"):
                limit = self._extract_limit(default=5)
                return QueryHandlers.get_top_customers(limit)
            if QueryLexicon.has_any(query_lower, "summary"):
                return QueryHandlers.get_customer_stats()
            if QueryLexicon.has_any(query_lower, "debt"):
                return None
            customer_term = QueryLexicon.remove_terms(
                self.query,
                "customer", "list", "summary", "debt",
                extra=["detail", "details", "profile", "info", "balance", "for"]
            )
            if QueryLexicon.has_any(query_lower, "list"):
                return QueryHandlers.search_customers(customer_term)
            if customer_term:
                return QueryHandlers.get_customer_profile(customer_term)
            return QueryHandlers.get_customer_stats()
        customer_words = ['customer', 'customers', 'ဝယ်သူ', 'ဝယ်ယူသူ', 'ဖောက်သည်']

        if not any(word in query_lower for word in customer_words):
            return None

        if any(word in query_lower for word in ['top', 'best']):
            match = re.search(r'(\d+)', query_lower)
            limit = int(match.group(1)) if match else 5
            return QueryHandlers.get_top_customers(limit)

        if any(word in query_lower for word in ['stats', 'statistics', 'summary', 'စာရင်းအင်း']):
            return QueryHandlers.get_customer_stats()

        if any(word in query_lower for word in ['debt', 'credit', 'အကြွေး']):
            return None

        search_patterns = [
            r'(?:search|find|show)\s+(?:customer|customers)\s+["\']?([^"\']+)["\']?',
            r'(?:customer|customers)\s+(?:search|find)\s+["\']?([^"\']+)["\']?',
            r'(?:search|find|show).*(?:ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်)\s*["\']?([^"\']+)["\']?',
            r'(?:ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်).*(?:ရှာ|ရှာဖွေ)\s*["\']?([^"\']+)["\']?',
        ]
        for pattern in search_patterns:
            match = re.search(pattern, self.query, re.IGNORECASE)
            if match:
                return QueryHandlers.search_customers(self._clean_customer_term(match.group(1)))

        detail_patterns = [
            r'(?:customer|customers)\s+(?:detail|details|profile|info|balance)\s+["\']?([^"\']+)["\']?',
            r'(?:detail|details|profile|info|balance)\s+(?:for\s+)?(?:customer|customers)\s+["\']?([^"\']+)["\']?',
            r'^(?:customer|customers)\s+["\']?([^"\']+)["\']?',
            r'(?:ဝယ်သူ|ဝယ်ယူသူ|ဖောက်သည်).*(?:အသေးစိတ်|အချက်အလက်|လက်ကျန်)\s*["\']?([^"\']+)["\']?',
        ]
        for pattern in detail_patterns:
            match = re.search(pattern, self.query, re.IGNORECASE)
            if match:
                return QueryHandlers.get_customer_profile(self._clean_customer_term(match.group(1)))

        return QueryHandlers.get_customer_stats()

    def _clean_customer_term(self, term):
        term = (term or "").strip().strip('"\'')
        removable = [
            'customer', 'customers', 'detail', 'details', 'profile', 'info', 'balance',
            'search', 'find', 'show', 'for', 'ဝယ်သူ', 'ဝယ်ယူသူ', 'ဖောက်သည်',
            'ရှာ', 'ရှာဖွေ', 'အသေးစိတ်', 'အချက်အလက်', 'လက်ကျန်'
        ]
        for word in removable:
            term = re.sub(rf'\b{re.escape(word)}\b', '', term, flags=re.IGNORECASE).strip()
        return term

    def _check_debt_query(self):
        """🔥 Check if query is a debt-related query"""
        query_lower = self.query.lower().strip()
        
        if QueryLexicon.has_any(query_lower, "debt"):
            if QueryLexicon.has_any(query_lower, "overdue"):
                return QueryHandlers.get_overdue_debts()
            if "\u1021\u1000\u103c\u103d\u1031\u1038" in query_lower and "\u1005\u102c\u101b\u1004\u103a\u1038" in query_lower:
                return QueryHandlers.get_debt_summary()
            if QueryLexicon.has_any(query_lower, "summary") or query_lower in QueryLexicon.words("debt"):
                return QueryHandlers.get_debt_summary()
            if QueryLexicon.has_any(query_lower, "list"):
                return QueryHandlers.get_recent_debts()

            potential_name = QueryLexicon.remove_terms(
                self.query,
                "debt", "customer", "summary", "list", "overdue",
                extra=["for", "of", "show", "check", "find"]
            )
            if potential_name:
                return QueryHandlers.get_customer_debt(potential_name)
            return QueryHandlers.get_debt_summary()

        # Debt summary keywords
        debt_summary_keywords = [
            'အကြွေးစာရင်း', 'အကြွေး', 'ချေးငွေ', 'အကြွေးအကျဉ်းချုပ်',
            'debt summary', 'debt overview', 'credit summary', 'debt'
        ]
        
        # Check if it's a debt summary query
        is_debt_summary = False
        for kw in debt_summary_keywords:
            if kw in query_lower:
                is_debt_summary = True
                break
        
        # Exact match for common debt queries
        if query_lower in ['အကြွေးစာရင်း', 'အကြွေး', 'ချေးငွေ', 'debt', 'debt summary']:
            is_debt_summary = True
        
        if is_debt_summary:
            return QueryHandlers.get_debt_summary()
        
        # Customer debt with name
        customer_debt_patterns = [
            r'(?:customer debt|debt customer|အကြွေး)\s+["\']?([^"\']+)["\']?',
            r'(["\']?[^"\']+["\']?)\s*(?:debt|အကြွေး)',
            r'(?:debt|အကြွေး)\s+(?:for|အတွက်)\s+["\']?([^"\']+)["\']?',
        ]
        
        for pattern in customer_debt_patterns:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip().strip('"\'')
                if potential_name.lower() not in ['debt', 'အကြွေး', 'customer', 'ဖောက်သည်', 'summary', 'စာရင်း']:
                    return QueryHandlers.get_customer_debt(potential_name)
        
        # Overdue debts
        overdue_keywords = [
            'overdue', 'overdue debt', 'overdue debts', 
            'ကြာမြင့်', 'ကြာမြင့်အကြွေး', 'ကြာမြင့်အကြွေးများ',
            'late payment', 'နောက်ကျ', 'သတ်မှတ်ရက်ကျော်'
        ]
        if any(kw in query_lower for kw in overdue_keywords):
            return QueryHandlers.get_overdue_debts()
        
        # Recent debts
        recent_keywords = [
            'recent debt', 'recent debts', 
            'မကြာသေးမီအကြွေး', 'မကြာသေးမီအကြွေးများ',
            'နောက်ဆုံးအကြွေး', 'recent credit'
        ]
        if any(kw in query_lower for kw in recent_keywords):
            return QueryHandlers.get_recent_debts()
        
        return None
    
    def _route_new_intent(self, intent: str, intent_result: dict) -> dict:
        """🆕 Route new intents (product_search, add_to_cart, troubleshoot, settings)"""
        query = self.query
        entities = intent_result.get('entities', {})
        
        if intent == 'product_search':
            search_term = entities.get('search_term', query)
            results = AIProductSearch.search(search_term)
            return self._format_product_search_results(results, search_term)
        
        elif intent == 'add_to_cart':
            product_name = entities.get('product_name', query)
            # Clean up the product name
            for word in ['add', 'cart', 'ထည့်', 'ကတ်', 'to']:
                product_name = product_name.replace(word, '').strip()
            product = AIProductSearch.quick_add_to_cart(product_name)
            if product:
                return {
                    'type': 'add_to_cart',
                    'data': [product],
                    'message': f"✅ Added '{product['name']}' to cart!\n"
                              f"💰 Price: {product['price']} Ks\n"
                              f"📦 Stock: {product['stock']} units",
                    'sql': '',
                    'product': product
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"❌ Product not found for: '{product_name}'\n"
                              f"💡 Try searching with a different term.",
                    'sql': ''
                }
        
        elif intent == 'check_stock':
            product_name = entities.get('product_name', query)
            for word in ['stock', 'စတော့', 'how many', 'ဘယ်လောက်', 'available', 'ကျန်', 'ရှိ']:
                product_name = product_name.replace(word, '').strip()
            results = AIProductSearch.search(product_name, limit=1)
            if results:
                p = results[0]
                return {
                    'type': 'check_stock',
                    'data': [p],
                    'message': f"📦 **{p['name']}**\n"
                              f"• Stock: {p['stock']} units\n"
                              f"• Price: {p['price']} Ks\n"
                              f"• Category: {p['category']}",
                    'sql': ''
                }
            else:
                return {
                    'type': 'response',
                    'data': [],
                    'message': f"❌ Product not found: '{product_name}'",
                    'sql': ''
                }
        
        elif intent == 'troubleshoot':
            trouble = AITroubleshooter.troubleshoot(query)
            return {
                'type': 'troubleshoot',
                'data': [],
                'message': self._format_troubleshoot_response(trouble),
                'sql': '',
                'trouble_data': trouble
            }
        
        elif intent == 'settings':
            settings = AISettingsAssistant.parse_command(query)
            return {
                'type': 'settings',
                'data': [],
                'message': settings.get('response', "✅ Setting updated!"),
                'sql': '',
                'settings_action': settings
            }
        
        return None
    
    def _route_by_intent(self, intent_result: dict) -> dict:
        """Route query based on detected intent"""
        intent = intent_result.get('intent', 'unknown')
        entities = intent_result.get('entities', {})
        
        # 🔥 If this is a debt intent, handle it here (but this shouldn't be reached)
        # because _check_debt_query() already handles it and returns
        debt_intents = ['debt_summary', 'customer_debt', 'overdue_debts', 'recent_debts']
        if intent in debt_intents:
            # This should not happen because _check_debt_query() already handled it
            # But just in case, handle it here too
            if intent == 'debt_summary':
                return QueryHandlers.get_debt_summary()
            elif intent == 'customer_debt':
                customer_name = entities.get('customer_name', '')
                if customer_name:
                    return QueryHandlers.get_customer_debt(customer_name)
                return QueryHandlers.get_debt_summary()
            elif intent == 'overdue_debts':
                return QueryHandlers.get_overdue_debts()
            elif intent == 'recent_debts':
                return QueryHandlers.get_recent_debts()
        
        # Intent to handler mapping
        handlers = {
            'sales_today': QueryHandlers.get_today_sales,
            'sales_yesterday': QueryHandlers.get_yesterday_sales,
            'sales_weekly': QueryHandlers.get_weekly_sales,
            'sales_monthly': QueryHandlers.get_monthly_sales,
            'sales_total': QueryHandlers.get_total_sales,
            'top_products': lambda: QueryHandlers.get_top_products(entities.get('limit', 5)),
            'low_stock': QueryHandlers.get_low_stock_products,
            'stock_summary': QueryHandlers.get_stock_summary,
            'profit': QueryHandlers.get_profit_summary,
            'top_customers': lambda: QueryHandlers.get_top_customers(entities.get('limit', 5)),
            'customer_stats': QueryHandlers.get_customer_stats,
            'customer_search': lambda: QueryHandlers.search_customers(entities.get('search_term', '')),
            'customer_detail': lambda: QueryHandlers.get_customer_profile(entities.get('customer_name', '')),
            'expenses_today': QueryHandlers.get_today_expenses,
            'expenses_monthly': QueryHandlers.get_monthly_expenses,
            'expenses_total': QueryHandlers.get_total_expenses,
            'product_search': lambda: QueryHandlers.search_products(entities.get('search_term', '')),
            'product_detail': lambda: QueryHandlers.get_product_details(entities.get('identifier', '')),
            'help': self._get_help_response,
        }
        
        handler = handlers.get(intent)
        if handler:
            return handler()
        
        # Try product detail detection
        if 'identifier' in entities:
            return QueryHandlers.get_product_details(entities['identifier'])
        
        # Fallback
        return self._get_fallback_response()
    
    def _enhance_response(self, result: dict, intent_result: dict) -> dict:
        """Enhance response with templates"""
        intent = intent_result.get('intent', '')
        
        # Only enhance sales responses
        if intent.startswith('sales_'):
            period = intent.replace('sales_', '')
            response = ResponseTemplates.get_sales_response(result, period)
            result['enhanced_message'] = response
        
        # Enhance stock responses
        elif intent == 'low_stock' and result.get('data'):
            response = ResponseTemplates.get_stock_response(result['data'])
            result['enhanced_message'] = response
        
        return result
    
    def _format_product_search_results(self, results, search_term):
        """Format product search results"""
        if not results:
            return {
                'type': 'response',
                'data': [],
                'message': f"❌ No products found for: '{search_term}'\n\n"
                          f"💡 Try:\n"
                          f"• Checking spelling\n"
                          f"• Using a different term\n"
                          f"• Searching by category",
                'sql': ''
            }
        
        message = f"🔍 **Found {len(results)} products for '{search_term}':**\n\n"
        for i, p in enumerate(results[:10], 1):
            stock_emoji = "🟢" if p['stock'] > 10 else "🟡" if p['stock'] > 0 else "🔴"
            message += f"{i}. {p['name']} - {p['price']} Ks {stock_emoji} (Stock: {p['stock']})\n"
        
        if len(results) > 10:
            message += f"\n... and {len(results) - 10} more results"
        
        return {
            'type': 'product_search',
            'data': results,
            'message': message,
            'sql': ''
        }
    
    def _format_troubleshoot_response(self, trouble):
        """Format troubleshooting response"""
        msg = f"🛠️ **{trouble['issue']}**\n\n"
        
        msg += "**💡 Solutions:**\n"
        for solution in trouble['solutions']:
            msg += f"• {solution}\n"
        
        msg += "\n**📋 Steps:**\n"
        for step in trouble['steps']:
            msg += f"{step}\n"
        
        if trouble.get('quick_fix'):
            msg += f"\n{trouble['quick_fix']}"
        
        return msg
    
    def _get_help_response(self) -> dict:
        """Get help response based on language"""
        is_myanmar = self.nlp.is_myanmar_query(self.query)
        help_text = QueryHandlers.get_help_text_myanmar() if is_myanmar else QueryHandlers.get_help_text()
        
        return {
            'type': 'response',
            'data': [],
            'message': help_text,
            'sql': ''
        }
    
    def _get_fallback_response(self) -> dict:
        """Get fallback response"""
        is_myanmar = self.nlp.is_myanmar_query(self.query)
        
        if is_myanmar:
            message = "❌ နားမလည်ပါ။ ကျေးဇူးပြု၍ အောက်ပါမေးခွန်းများကို မေးမြန်းပါ:\n\n" + QueryHandlers.get_help_text_myanmar()
        else:
            message = "❌ I don't understand. Please ask one of these questions:\n\n" + QueryHandlers.get_help_text()
        
        return {
            'type': 'response',
            'data': [],
            'message': message,
            'sql': ''
        }
