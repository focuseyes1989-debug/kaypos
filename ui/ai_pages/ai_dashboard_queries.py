"""Permission-aware, read-only Dashboard data foundation for AI Chat."""

import re
import calendar
from datetime import date, timedelta

from models.database import connect_db
from ui.ai_pages.ai_employee_queries import EmployeeQueryHandler
from utils.db_compat import is_postgres_backend, table_exists
from utils.permissions import PermissionManager


class AIDashboardQueryHandler:
    """Return Dashboard metrics using the same definitions as DashboardPage."""

    REQUIRED_PERMISSION = "dashboard"

    @classmethod
    def handles(cls, query):
        text = (query or "").lower()
        has_dashboard = any(word in text for word in (
            "dashboard", "ဒက်ရှ်ဘုတ်", "ဒက်ရှ်ဘော့", "ပင်မစာမျက်နှာ",
            "my sales", "ကိုယ်ပိုင်အရောင်း", "ကျွန်တော့်အရောင်း", "ကျွန်တော့်အရောင်း", "ကျွန်မအရောင်း",
        ))
        has_request = any(word in text for word in ("summary", "overview", "data", "cards", "metrics", "why", "reason", "explain", "cause", "alert", "warning", "anomaly", "unusual", "chart", "trend", "graph", "top", "payment", "category", "compare", "comparison", "vs", "ပြ", "အကျဉ်းချုပ်", "အခြေအနေ", "ဘာကြောင့်", "ဘာလို့", "အကြောင်းရင်း", "ရှင်းပြ", "သတိ", "ပုံမှန်မဟုတ်", "နှိုင်း", "တိုးလား", "လျော့လား", "ဂရပ်", "ဇယား"))
        return has_dashboard and has_request

    @classmethod
    def handle(cls, query, user_id):
        if not cls.handles(query):
            return None
        permissions = cls._permissions(user_id)
        context=cls._user_context(user_id)
        personal=cls._wants_personal(query) or ("dashboard" not in permissions and "sales" in permissions)
        if personal:
            return cls._personal(query,user_id,permissions,context)
        if cls.REQUIRED_PERMISSION not in permissions:
            return cls._result("🔒 You don't have permission to view Dashboard information.", [], None, None)
        if cls._is_explanation(query):
            return cls._explain(query,permissions)
        if cls._is_alert(query):
            return cls._alerts(query, permissions)
        if cls._is_comparison(query):
            return cls._comparison(query, permissions)
        if cls._is_chart(query):
            return cls._chart(query, permissions)
        start, end = EmployeeQueryHandler._date_range(query)
        try:
            metrics = cls.collect(start, end, permissions)
        except Exception as exc:
            return cls._result(f"❌ Dashboard summary failed: {exc}", [], start, end)
        return cls._result(cls._message(metrics, start, end), cls._rows(metrics), start, end, metrics)

    @staticmethod
    def _wants_personal(query):
        text=(query or "").lower()
        return any(word in text for word in (
            "my dashboard", "my sales", "personal dashboard", "ကိုယ်ပိုင် dashboard",
            "ကျွန်တော့် dashboard", "ကျွန်တော့် dashboard", "ကျွန်မ dashboard", "မိမိ dashboard",
            "ကိုယ်ပိုင်အရောင်း", "ကျွန်တော့်အရောင်း", "ကျွန်တော့်အရောင်း", "ကျွန်မအရောင်း",
        ))

    @staticmethod
    def _user_context(user_id):
        try:user_id=int(user_id)
        except (TypeError,ValueError):return {}
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("""SELECT u.id,u.username,u.role,e.id,e.employee_no,e.full_name
                FROM users u LEFT JOIN employees e ON e.user_id=u.id WHERE u.id=?""",(user_id,));row=cursor.fetchone()
            return {"user_id":row[0],"username":row[1],"role":row[2],"employee_id":row[3],"employee_no":row[4],"full_name":row[5]} if row else {}
        except Exception:return {}
        finally:conn.close()

    @classmethod
    def _personal(cls,query,user_id,permissions,context):
        if "sales" not in permissions:return cls._result("🔒 Sales permission is required for a personal Dashboard.",[],None,None)
        if not context.get("username"):return cls._result("🔍 The logged-in user could not be resolved for a personal Dashboard.",[],None,None)
        start,end=EmployeeQueryHandler._date_range(query)
        try:
            current=cls.collect_personal(start,end,context)
            if cls._is_alert(query):
                current_start,current_end,previous_start,previous_end=cls.comparison_periods(query);current=cls.collect_personal(current_start,current_end,context);previous=cls.collect_personal(previous_start,previous_end,context);alerts=cls.evaluate_alerts(current,previous);message=("⚠️ **Personal operational alerts**\n\n"+"\n".join(f"• {row['Severity']} — {row['Title']}: {row['Evidence']}" for row in alerts)) if alerts else "✅ No personal rule-based alerts were triggered."
                result=cls._alert_result(message,alerts,current_start,current_end,previous_start,previous_end,current,previous);result.update({"scope":"personal","scope_label":context.get("full_name") or context["username"]});return result
            if cls._is_explanation(query):
                return cls._result("ℹ️ Personal change explanations currently support period comparison only. Try `my dashboard this month compare`.",[],start,end)
            if cls._is_comparison(query):
                current_start,current_end,previous_start,previous_end=cls.comparison_periods(query);current=cls.collect_personal(current_start,current_end,context);previous=cls.collect_personal(previous_start,previous_end,context);changes=cls.compare_metrics(current,previous)
                result=cls._comparison_result(cls._comparison_message(changes,current_start,current_end,previous_start,previous_end),list(changes.values()),current_start,current_end,previous_start,previous_end,current,previous,changes)
                result.update({"scope":"personal","scope_label":context.get("full_name") or context["username"]});return result
            if cls._is_chart(query):
                chart_kind=cls._chart_kind(query)
                if chart_kind in ("sales_expenses","profit"):
                    result=cls._chart_result("🔒 Company expense and net-profit charts are not included in a personal Dashboard.",[],chart_kind,start,end);result.update({"scope":"personal","scope_label":context.get("full_name") or context["username"]});return result
                data,actual_start,actual_end=cls.collect_personal_chart(chart_kind,start,end,context)
                result=cls._chart_result(f"📉 **Personal Dashboard Chart — {actual_start} to {actual_end}**\n\n{len(data)} authorized point(s).",data,chart_kind,actual_start,actual_end);result.update({"scope":"personal","scope_label":context.get("full_name") or context["username"]});return result
        except Exception as exc:return cls._result(f"❌ Personal Dashboard failed: {exc}",[],start,end)
        label=context.get("full_name") or context["username"];message=cls._personal_message(current,start,end,label)
        result=cls._result(message,cls._rows(current),start,end,current);result.update({"scope":"personal","scope_label":label});return result

    @classmethod
    def collect_personal(cls,start,end,context):
        conn=connect_db();cursor=conn.cursor();day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)";username=context["username"]
        metrics={"gross_sales":0.0,"discounts":0.0,"refunds":0.0,"net_sales":0.0,"transactions":0,"cogs":0.0,"gross_profit":0.0,"expenses":None,"net_profit":None,"outstanding_credit":None,"low_stock":None,"out_of_stock":None,"open_cash_sessions":0,"attendance_issues":None,"attendance_records":None}
        try:
            cursor.execute(f"""SELECT COALESCE(SUM(si.qty*si.price),0),COUNT(DISTINCT s.id) FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ?""",(username,start,end));row=cursor.fetchone() or (0,0);metrics["gross_sales"]=float(row[0] or 0);metrics["transactions"]=int(row[1] or 0)
            cursor.execute(f"SELECT COALESCE(SUM(s.discount_amount),0) FROM sales s WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ?",(username,start,end));metrics["discounts"]=float((cursor.fetchone() or (0,))[0] or 0)
            cursor.execute(f"""SELECT COALESCE(SUM(si.qty*si.price),0) FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id WHERE s.status='refunded' AND s.created_by=? AND {day} BETWEEN ? AND ?""",(username,start,end));metrics["refunds"]=float((cursor.fetchone() or (0,))[0] or 0);metrics["net_sales"]=metrics["gross_sales"]-metrics["discounts"]-metrics["refunds"]
            cursor.execute(f"""SELECT COALESCE(SUM(p.cost*si.qty),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id JOIN products p ON p.id=si.product_id OR (si.product_id IS NULL AND p.name=si.product_name) WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ? AND (p.sold_by IS NULL OR p.sold_by!='Service')""",(username,start,end));metrics["cogs"]=float((cursor.fetchone() or (0,))[0] or 0);metrics["gross_profit"]=metrics["net_sales"]-metrics["cogs"]
            employee_id=context.get("employee_id")
            if employee_id and table_exists(cursor,"cash_sessions"):
                cursor.execute("SELECT COUNT(*) FROM cash_sessions WHERE employee_id=? AND LOWER(COALESCE(status,''))='open'",(employee_id,));metrics["open_cash_sessions"]=int((cursor.fetchone() or (0,))[0] or 0)
            if employee_id and table_exists(cursor,"attendance"):
                attendance_day="CAST(NULLIF(attendance_date,'') AS DATE)" if is_postgres_backend() else "date(attendance_date)";cursor.execute(f"""SELECT COUNT(*),COALESCE(SUM(CASE WHEN LOWER(COALESCE(status,'')) IN ('late','incomplete','absent','half-day') THEN 1 ELSE 0 END),0) FROM attendance WHERE employee_id=? AND {attendance_day} BETWEEN ? AND ?""",(employee_id,start,end));attendance=cursor.fetchone() or (0,0);metrics["attendance_records"]=int(attendance[0] or 0);metrics["attendance_issues"]=int(attendance[1] or 0)
            return metrics
        finally:conn.close()

    @classmethod
    def collect_personal_chart(cls,kind,start,end,context):
        start_day,end_day=date.fromisoformat(start),date.fromisoformat(end)
        if (end_day-start_day).days>30:start_day=end_day-timedelta(days=30)
        start,end=start_day.isoformat(),end_day.isoformat();conn=connect_db();cursor=conn.cursor();username=context["username"];day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
        try:
            if kind=="payments":
                cursor.execute(f"SELECT COALESCE(s.payment_type,'Other'),COALESCE(SUM(s.total),0),COUNT(*) FROM sales s WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ? GROUP BY COALESCE(s.payment_type,'Other') ORDER BY 2 DESC",(username,start,end));return [{"Label":row[0],"Value":float(row[1] or 0),"Count":int(row[2] or 0)} for row in cursor.fetchall()],start,end
            if kind in ("top_products","categories"):
                label="COALESCE(si.product_name,'Unknown')" if kind=="top_products" else "COALESCE(p.category,'Uncategorized')";join="" if kind=="top_products" else "LEFT JOIN products p ON p.id=si.product_id OR (si.product_id IS NULL AND p.name=si.product_name)"
                cursor.execute(f"SELECT {label},COALESCE(SUM(si.qty*si.price),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id {join} WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ? GROUP BY {label} ORDER BY 2 DESC LIMIT 10",(username,start,end));return [{"Label":row[0],"Value":float(row[1] or 0)} for row in cursor.fetchall()],start,end
            cursor.execute(f"SELECT {day},COALESCE(SUM(s.total),0),COUNT(*) FROM sales s WHERE s.status='completed' AND s.created_by=? AND {day} BETWEEN ? AND ? GROUP BY {day} ORDER BY {day}",(username,start,end));data=[{"Date":str(row[0]),"Sales":float(row[1] or 0),"Transactions":int(row[2] or 0)} for row in cursor.fetchall()];return data,start,end
        finally:conn.close()

    @staticmethod
    def _personal_message(metrics,start,end,label):
        lines=[f"👤 **Personal Dashboard — {label} — {start} to {end}**","",f"• Net sales: {float(metrics['net_sales'] or 0):,.0f} Ks",f"• Transactions: {int(metrics['transactions'] or 0)}",f"• Gross profit: {float(metrics['gross_profit'] or 0):,.0f} Ks",f"• Refunds: {float(metrics['refunds'] or 0):,.0f} Ks",f"• Open cash sessions: {int(metrics['open_cash_sessions'] or 0)}"]
        if metrics.get("attendance_records") is not None:lines.append(f"• Own attendance issues: {int(metrics.get('attendance_issues') or 0)} of {int(metrics['attendance_records'])} record(s)")
        lines.extend(["","This view is restricted to sales and employee records mapped to the logged-in account. Company expenses, credit and stock are not included."]);return "\n".join(lines)

    @staticmethod
    def _is_comparison(query):
        text = (query or "").lower()
        return any(word in text for word in ("compare", "comparison", " vs ", "versus", "နှိုင်း", "ထက်တိုး", "ထက် တိုး", "ထက်လျော့", "ထက် လျော့", "တိုးလား", "လျော့လား"))

    @staticmethod
    def _is_alert(query):
        text=(query or "").lower()
        return any(word in text for word in ("alert", "alerts", "warning", "warnings", "anomaly", "unusual", "risk", "သတိထား", "သတိပေး", "ပုံမှန်မဟုတ်", "အန္တရာယ်"))

    @staticmethod
    def _is_explanation(query):
        text=(query or "").lower()
        return any(word in text for word in ("why", "reason", "explain", "cause", "ဘာကြောင့်", "ဘာကြောင့်", "ဘာလို့", "အကြောင်းရင်း", "ရှင်းပြ"))

    @staticmethod
    def _explanation_focus(query):
        text=(query or "").lower()
        if any(word in text for word in ("expense", "expenses", "cost increase", "ကုန်ကျစရိတ်", "အသုံးစရိတ်")):return "expenses"
        if any(word in text for word in ("profit", "margin", "အမြတ်")):return "profit"
        return "sales"

    @classmethod
    def _explain(cls,query,permissions):
        focus=cls._explanation_focus(query);required={"sales_summary"} if focus=="sales" else {"expense"} if focus=="expenses" else {"sales_summary","expense"}
        missing=required-set(permissions)
        if missing:
            return cls._explanation_result("🔒 Detailed change analysis requires: "+", ".join(sorted(missing))+".",[],focus,None,None,None,None)
        current_start,current_end,previous_start,previous_end=cls.comparison_periods(query)
        try:data=cls.collect_explanation(focus,current_start,current_end,previous_start,previous_end)
        except Exception as exc:return cls._explanation_result(f"❌ Dashboard change analysis failed: {exc}",[],focus,current_start,current_end,previous_start,previous_end)
        title={"sales":"Sales change","expenses":"Expense change","profit":"Net-profit change"}[focus]
        lines=[f"🔍 **{title} evidence — {current_start} to {current_end}**","",f"Compared with {previous_start} to {previous_end}.",""]
        if data:
            for row in data[:8]:lines.append(f"• {row['Dimension']} — {row['Segment']}: current {row['Current']:,.0f} Ks, previous {row['Previous']:,.0f} Ks, impact {row['Impact']:+,.0f} Ks")
        else:lines.append("No recorded breakdown changes were found for these periods.")
        lines.extend(["","Each dimension is an alternative view and must not be added to another dimension. Product/category use item gross values; payment/cashier use recorded sale totals. These are confirmed arithmetic changes, but do not by themselves prove the business cause."])
        return cls._explanation_result("\n".join(lines),data,focus,current_start,current_end,previous_start,previous_end)

    @classmethod
    def collect_explanation(cls,focus,current_start,current_end,previous_start,previous_end):
        conn=connect_db();cursor=conn.cursor();sale_day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)";expense_day="CAST(NULLIF(e.expense_date,'') AS DATE)" if is_postgres_backend() else "date(e.expense_date)"
        sales_dimensions=(
            ("Product",f"""SELECT COALESCE(si.product_name,'Unknown'),COALESCE(SUM(si.qty*si.price),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ? GROUP BY COALESCE(si.product_name,'Unknown')"""),
            ("Category",f"""SELECT COALESCE(p.category,'Uncategorized'),COALESCE(SUM(si.qty*si.price),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN products p ON p.id=si.product_id OR (si.product_id IS NULL AND p.name=si.product_name) WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ? GROUP BY COALESCE(p.category,'Uncategorized')"""),
            ("Payment",f"""SELECT COALESCE(s.payment_type,'Other'),COALESCE(SUM(s.total),0) FROM sales s WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ? GROUP BY COALESCE(s.payment_type,'Other')"""),
            ("Cashier",f"""SELECT COALESCE(s.created_by,'Unknown'),COALESCE(SUM(s.total),0) FROM sales s WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ? GROUP BY COALESCE(s.created_by,'Unknown')"""),
        )
        expense_dimensions=(
            ("Expense Category",f"""SELECT COALESCE(e.category,'Uncategorized'),COALESCE(SUM(e.amount),0) FROM expenses e WHERE {expense_day} BETWEEN ? AND ? GROUP BY COALESCE(e.category,'Uncategorized')"""),
            ("Expense Payment",f"""SELECT COALESCE(e.payment_method,'Other'),COALESCE(SUM(e.amount),0) FROM expenses e WHERE {expense_day} BETWEEN ? AND ? GROUP BY COALESCE(e.payment_method,'Other')"""),
            ("Expense Recorder",f"""SELECT COALESCE(e.created_by,'Unknown'),COALESCE(SUM(e.amount),0) FROM expenses e WHERE {expense_day} BETWEEN ? AND ? GROUP BY COALESCE(e.created_by,'Unknown')"""),
        )
        dimensions=sales_dimensions if focus=="sales" else expense_dimensions if focus=="expenses" else sales_dimensions+expense_dimensions
        rows=[]
        try:
            for dimension,sql in dimensions:
                current=cls._dimension_values(cursor,sql,current_start,current_end);previous=cls._dimension_values(cursor,sql,previous_start,previous_end)
                for segment in set(current)|set(previous):
                    change=current.get(segment,0)-previous.get(segment,0);is_expense=dimension.startswith("Expense");impact=-change if focus=="profit" and is_expense else change
                    if change:rows.append({"Dimension":dimension,"Segment":segment,"Current":current.get(segment,0),"Previous":previous.get(segment,0),"Change":change,"Impact":impact})
            rows.sort(key=lambda row:abs(row["Impact"]),reverse=True);return rows[:30]
        finally:conn.close()

    @staticmethod
    def _dimension_values(cursor,sql,start,end):
        cursor.execute(sql,(start,end));return {str(row[0] or "Unknown"):float(row[1] or 0) for row in cursor.fetchall()}

    @classmethod
    def _alerts(cls,query,permissions):
        current_start,current_end,previous_start,previous_end=cls.comparison_periods(query)
        try:
            current=cls.collect(current_start,current_end,permissions);previous=cls.collect(previous_start,previous_end,permissions)
            alerts=cls.evaluate_alerts(current,previous)
        except Exception as exc:
            return cls._alert_result(f"❌ Dashboard alerts failed: {exc}",[],current_start,current_end,previous_start,previous_end)
        if alerts:
            lines=[f"⚠️ **Operational Alerts — {current_start} to {current_end}**","",f"Compared with {previous_start} to {previous_end}.",""]
            for item in alerts:lines.append(f"• **{item['Severity']} — {item['Title']}**: {item['Evidence']} {item['Action']}")
            message="\n".join(lines)+"\n\nThese are deterministic operational rules, not predictions. Review the linked source page before acting."
        else:
            message=(f"✅ **No rule-based operational alerts — {current_start} to {current_end}**\n\n"
                     f"Compared with {previous_start} to {previous_end}. No configured threshold was triggered. This does not guarantee that every business risk is absent.")
        return cls._alert_result(message,alerts,current_start,current_end,previous_start,previous_end,current,previous)

    @staticmethod
    def evaluate_alerts(current,previous):
        alerts=[]
        def add(severity,title,evidence,action,target,tab=None):
            alerts.append({"Severity":severity,"Title":title,"Evidence":evidence,"Action":action,"Target":target,"Tab":tab})
        sales=float(current.get("net_sales") or 0);previous_sales=float(previous.get("net_sales") or 0)
        expenses=float(current.get("expenses") or 0);previous_expenses=float(previous.get("expenses") or 0)
        if previous_sales>0 and sales<previous_sales*0.80:
            decline=(previous_sales-sales)/previous_sales*100;add("Critical" if decline>=40 else "Warning","Sales decline",f"Net sales fell {decline:.1f}% ({sales:,.0f} vs {previous_sales:,.0f} Ks).","Review sales breakdown.","sales_summary","items")
        if previous_expenses>0 and expenses>previous_expenses*1.25:
            increase=(expenses-previous_expenses)/previous_expenses*100;add("Critical" if increase>=50 else "Warning","Expense increase",f"Expenses rose {increase:.1f}% ({expenses:,.0f} vs {previous_expenses:,.0f} Ks).","Review expense categories.","expense","charts")
        current_margin=(float(current.get("gross_profit") or 0)/sales*100) if sales else None
        previous_margin=(float(previous.get("gross_profit") or 0)/previous_sales*100) if previous_sales else None
        if current_margin is not None and previous_margin is not None and previous_margin-current_margin>=5:
            drop=previous_margin-current_margin;add("Warning","Margin decline",f"Gross margin fell {drop:.1f} points ({current_margin:.1f}% vs {previous_margin:.1f}%).","Review products and discounts.","sales_summary","top_products")
        if float(current.get("net_profit") or 0)<0:
            add("Critical","Net loss",f"Net profit is {float(current['net_profit']):,.0f} Ks.","Review sales and expenses.","expense","charts")
        refund_rate=(float(current.get("refunds") or 0)/float(current.get("gross_sales") or 0)*100) if float(current.get("gross_sales") or 0)>0 else 0
        if refund_rate>=5:
            add("Critical" if refund_rate>=10 else "Warning","High refund rate",f"Refunds equal {refund_rate:.1f}% of gross sales.","Review refunded receipts.","receipts","refunds")
        if int(current.get("out_of_stock") or 0)>0:
            add("Critical","Out of stock",f"{int(current['out_of_stock'])} product(s) have no stock.","Review inventory.","inventory","low_stock")
        elif int(current.get("low_stock") or 0)>0:
            add("Warning","Low stock",f"{int(current['low_stock'])} product(s) are at or below their threshold.","Review inventory.","inventory","low_stock")
        if current.get("attendance_records") is not None and int(current.get("attendance_records") or 0)>0:
            rate=int(current.get("attendance_issues") or 0)/int(current["attendance_records"])*100
            if rate>=10:add("Critical" if rate>=25 else "Warning","Attendance issues",f"{int(current.get('attendance_issues') or 0)} of {int(current['attendance_records'])} records ({rate:.1f}%) have issues.","Review attendance filters.","employees","attendance")
        if current.get("open_cash_sessions"):
            add("Info","Open cash sessions",f"{int(current['open_cash_sessions'])} session(s) are open.","Confirm they are expected before closing.","employees","cash_sessions")
        if current.get("outstanding_credit"):
            add("Info","Outstanding credit",f"Current outstanding credit is {float(current['outstanding_credit']):,.0f} Ks.","Review customer balances.","customers","outstanding")
        order={"Critical":0,"Warning":1,"Info":2};alerts.sort(key=lambda item:order[item["Severity"]])
        return alerts[:10]

    @staticmethod
    def _is_chart(query):
        text = (query or "").lower()
        return any(word in text for word in ("chart", "trend", "graph", "payment breakdown", "top products", "top categories", "ဂရပ်", "ဇယား", "လမ်းကြောင်း"))

    @classmethod
    def _chart(cls, query, permissions):
        start, end = EmployeeQueryHandler._date_range(query)
        kind = cls._chart_kind(query)
        try:
            data, actual_start, actual_end = cls.collect_chart(kind, start, end)
        except Exception as exc:
            return cls._chart_result(f"❌ Dashboard chart failed: {exc}", [], kind, start, end)
        title = {
            "daily_sales": "Daily Sales Trend", "sales_expenses": "Sales vs Expenses",
            "profit": "Gross and Net Profit", "transactions": "Transaction Trend",
            "payments": "Payment Method Breakdown", "top_products": "Top Products",
            "categories": "Sales by Category",
        }[kind]
        limited = (actual_start, actual_end) != (start, end)
        note = " The chart is limited to the most recent 31 days." if limited else ""
        message = f"📉 **{title} — {actual_start} to {actual_end}**\n\n{len(data)} chart point(s).{note}"
        return cls._chart_result(message, data, kind, actual_start, actual_end)

    @staticmethod
    def _chart_kind(query):
        text = (query or "").lower()
        if any(word in text for word in ("payment", "ငွေပေးချေ", "payment method")):return "payments"
        if any(word in text for word in ("top product", "top item", "ထိပ်ဆုံးပစ္စည်း")):return "top_products"
        if any(word in text for word in ("category", "အမျိုးအစား")):return "categories"
        if any(word in text for word in ("transaction", "အရောင်းအကြိမ်")):return "transactions"
        if any(word in text for word in ("expense", "ကုန်ကျစရိတ်", "အသုံးစရိတ်")) and any(word in text for word in ("sales", "ရောင်းအား")):return "sales_expenses"
        if any(word in text for word in ("profit", "အမြတ်")):return "profit"
        return "daily_sales"

    @classmethod
    def collect_chart(cls, kind, start, end):
        start_day, end_day = date.fromisoformat(start), date.fromisoformat(end)
        if (end_day - start_day).days > 30:
            start_day = end_day - timedelta(days=30)
        start, end = start_day.isoformat(), end_day.isoformat()
        conn = connect_db(); cursor = conn.cursor()
        sale_day = "CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
        expense_day = "CAST(NULLIF(expense_date,'') AS DATE)" if is_postgres_backend() else "date(expense_date)"
        try:
            if kind == "payments":
                cursor.execute(f"""SELECT COALESCE(payment_type,'Other'),COALESCE(SUM(total),0),COUNT(*) FROM sales
                    WHERE status='completed' AND {sale_day} BETWEEN ? AND ?
                    GROUP BY COALESCE(payment_type,'Other') ORDER BY 2 DESC LIMIT 10""", (start,end))
                return [{"Label":str(row[0] or "Other"),"Value":float(row[1] or 0),"Count":int(row[2] or 0)} for row in cursor.fetchall()], start, end
            if kind == "top_products":
                cursor.execute(f"""SELECT si.product_name,COALESCE(SUM(si.qty),0),COALESCE(SUM(si.qty*si.price),0)
                    FROM sale_items si JOIN sales s ON s.id=si.sale_id
                    WHERE s.status='completed' AND {('CAST(s.created_at AS DATE)' if is_postgres_backend() else 'date(s.created_at)')} BETWEEN ? AND ?
                    GROUP BY si.product_name ORDER BY 3 DESC LIMIT 10""", (start,end))
                return [{"Label":str(row[0] or "Unknown"),"Quantity":float(row[1] or 0),"Value":float(row[2] or 0)} for row in cursor.fetchall()], start, end
            if kind == "categories":
                cursor.execute(f"""SELECT COALESCE(p.category,'Uncategorized'),COALESCE(SUM(si.qty*si.price),0)
                    FROM sale_items si JOIN sales s ON s.id=si.sale_id
                    LEFT JOIN products p ON si.product_id=p.id OR (si.product_id IS NULL AND si.product_name=p.name)
                    WHERE s.status='completed' AND {('CAST(s.created_at AS DATE)' if is_postgres_backend() else 'date(s.created_at)')} BETWEEN ? AND ?
                    GROUP BY COALESCE(p.category,'Uncategorized') ORDER BY 2 DESC LIMIT 10""", (start,end))
                return [{"Label":str(row[0]),"Value":float(row[1] or 0)} for row in cursor.fetchall()], start, end

            cursor.execute(f"""SELECT {sale_day},COALESCE(SUM(total),0),COUNT(*) FROM sales
                WHERE status='completed' AND {sale_day} BETWEEN ? AND ? GROUP BY {sale_day} ORDER BY {sale_day}""", (start,end))
            points = {str(row[0]):{"Date":str(row[0]),"Sales":float(row[1] or 0),"Transactions":int(row[2] or 0),"Expenses":0.0,"COGS":0.0} for row in cursor.fetchall()}
            cursor.execute(f"""SELECT {expense_day},COALESCE(SUM(amount),0) FROM expenses
                WHERE {expense_day} BETWEEN ? AND ? GROUP BY {expense_day} ORDER BY {expense_day}""", (start,end))
            for row in cursor.fetchall():
                key=str(row[0]);points.setdefault(key,{"Date":key,"Sales":0.0,"Transactions":0,"Expenses":0.0,"COGS":0.0})["Expenses"]=float(row[1] or 0)
            cogs_day = "CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
            cursor.execute(f"""SELECT {cogs_day},COALESCE(SUM(p.cost*si.qty),0)
                FROM sale_items si JOIN sales s ON s.id=si.sale_id
                JOIN products p ON si.product_id=p.id OR (si.product_id IS NULL AND si.product_name=p.name)
                WHERE s.status='completed' AND {cogs_day} BETWEEN ? AND ?
                  AND (p.sold_by IS NULL OR p.sold_by!='Service') GROUP BY {cogs_day}""", (start,end))
            for row in cursor.fetchall():
                key=str(row[0]);points.setdefault(key,{"Date":key,"Sales":0.0,"Transactions":0,"Expenses":0.0,"COGS":0.0})["COGS"]=float(row[1] or 0)
            data=[]
            for key in sorted(points):
                point=points[key];point["Gross Profit"]=point["Sales"]-point["COGS"];point["Net Profit"]=point["Gross Profit"]-point["Expenses"];data.append(point)
            return data, start, end
        finally:
            conn.close()

    @classmethod
    def _comparison(cls, query, permissions):
        current_start, current_end, previous_start, previous_end = cls.comparison_periods(query)
        try:
            current = cls.collect(current_start, current_end, permissions)
            previous = cls.collect(previous_start, previous_end, permissions)
        except Exception as exc:
            return cls._comparison_result(f"❌ Dashboard comparison failed: {exc}", [], current_start, current_end, previous_start, previous_end)
        changes = cls.compare_metrics(current, previous)
        message = cls._comparison_message(changes, current_start, current_end, previous_start, previous_end)
        return cls._comparison_result(message, list(changes.values()), current_start, current_end, previous_start, previous_end, current, previous, changes)

    @classmethod
    def comparison_periods(cls, query, today=None):
        """Return current and previous equal-length periods, inclusively."""
        today = today or date.today()
        text = (query or "").lower()
        explicit = [date.fromisoformat(value) for value in re.findall(r"\b20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b", text)]
        if len(explicit) >= 4:
            current_start, current_end = sorted(explicit[:2])
            previous_start, previous_end = sorted(explicit[2:4])
            return tuple(day.isoformat() for day in (current_start, current_end, previous_start, previous_end))
        if any(word in text for word in ("today", "ဒီနေ့", "ယနေ့")) and any(word in text for word in ("yesterday", "မနေ့က")):
            previous = today - timedelta(days=1)
            return today.isoformat(), today.isoformat(), previous.isoformat(), previous.isoformat()
        if any(word in text for word in ("this week", "current week", "ဒီအပတ်", "ဒီတစ်ပတ်")):
            current_start = today - timedelta(days=today.weekday())
            return cls._preceding_period(current_start, today)
        if any(word in text for word in ("this month", "current month", "ဒီလ", "ယခုလ")):
            current_start = today.replace(day=1)
            previous_month_end = current_start - timedelta(days=1)
            previous_start = previous_month_end.replace(day=1)
            previous_end = previous_start.replace(day=min(today.day, calendar.monthrange(previous_start.year, previous_start.month)[1]))
            return current_start.isoformat(), today.isoformat(), previous_start.isoformat(), previous_end.isoformat()
        if len(explicit) >= 2:
            current_start, current_end = sorted(explicit[:2])
            return cls._preceding_period(current_start, current_end)
        current_start, current_end = (date.fromisoformat(value) for value in EmployeeQueryHandler._date_range(query))
        return cls._preceding_period(current_start, current_end)

    @staticmethod
    def _preceding_period(current_start, current_end):
        days = (current_end - current_start).days + 1
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        return current_start.isoformat(), current_end.isoformat(), previous_start.isoformat(), previous_end.isoformat()

    @staticmethod
    def compare_metrics(current, previous):
        labels = {
            "net_sales": "Net Sales", "transactions": "Transactions", "discounts": "Discounts",
            "refunds": "Refunds", "cogs": "COGS", "gross_profit": "Gross Profit",
            "expenses": "Expenses", "net_profit": "Net Profit", "attendance_issues": "Attendance Issues",
        }
        result = {}
        for key, label in labels.items():
            current_value, previous_value = current.get(key), previous.get(key)
            if current_value is None or previous_value is None:
                continue
            change = float(current_value or 0) - float(previous_value or 0)
            percentage = (change / abs(float(previous_value)) * 100) if float(previous_value or 0) else (0.0 if not change else None)
            result[key] = {
                "Metric": label, "Current": current_value, "Previous": previous_value,
                "Change": change, "Change %": round(percentage, 1) if percentage is not None else None,
                "Direction": "up" if change > 0 else "down" if change < 0 else "flat",
            }
        return result

    @staticmethod
    def _comparison_message(changes, current_start, current_end, previous_start, previous_end):
        lines = [
            "📈 **Dashboard Period Comparison**", "",
            f"Current: {current_start} to {current_end}",
            f"Previous: {previous_start} to {previous_end}", "",
        ]
        for key in ("net_sales", "transactions", "gross_profit", "expenses", "net_profit", "refunds", "attendance_issues"):
            row = changes.get(key)
            if not row:
                continue
            percentage = "new from zero" if row["Change %"] is None else f"{row['Change %']:+.1f}%"
            suffix = "" if key in ("transactions", "attendance_issues") else " Ks"
            lines.append(f"• {row['Metric']}: {float(row['Current']):,.0f}{suffix} vs {float(row['Previous']):,.0f}{suffix} ({percentage})")
        lines.extend(["", "Current and previous periods contain the same number of days. Percentage change is unavailable when the previous value is zero."])
        return "\n".join(lines)

    @staticmethod
    def _permissions(user_id):
        try:
            return PermissionManager.get_user_permissions(int(user_id))
        except (TypeError, ValueError):
            return set()

    @classmethod
    def collect(cls, start, end, permissions):
        """Collect fixed read-only metrics; no user text is interpolated into SQL."""
        conn = connect_db()
        cursor = conn.cursor()
        sale_day = "CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
        expense_day = "CAST(NULLIF(expense_date, '') AS DATE)" if is_postgres_backend() else "date(expense_date)"
        attendance_day = "CAST(NULLIF(attendance_date, '') AS DATE)" if is_postgres_backend() else "date(attendance_date)"
        metrics = {
            "gross_sales": 0.0, "discounts": 0.0, "refunds": 0.0,
            "net_sales": 0.0, "transactions": 0, "cogs": 0.0,
            "gross_profit": 0.0, "expenses": 0.0, "net_profit": 0.0,
            "outstanding_credit": None, "low_stock": 0, "out_of_stock": 0,
            "open_cash_sessions": None, "attendance_issues": None, "attendance_records": None,
        }
        try:
            cursor.execute(f"""
                SELECT COALESCE(SUM(si.qty * si.price), 0), COUNT(DISTINCT s.id)
                FROM sales s LEFT JOIN sale_items si ON s.id=si.sale_id
                WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ?
            """, (start, end))
            row = cursor.fetchone() or (0, 0)
            metrics["gross_sales"], metrics["transactions"] = float(row[0] or 0), int(row[1] or 0)

            # Discounts belong to a sale, so aggregate them without the item
            # join to avoid counting one discount once per line item.
            sale_header_day = "CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
            cursor.execute(f"""SELECT COALESCE(SUM(discount_amount),0) FROM sales
                WHERE status='completed' AND {sale_header_day} BETWEEN ? AND ?""", (start, end))
            metrics["discounts"] = float((cursor.fetchone() or (0,))[0] or 0)

            cursor.execute(f"""
                SELECT COALESCE(SUM(si.qty * si.price), 0)
                FROM sales s LEFT JOIN sale_items si ON s.id=si.sale_id
                WHERE s.status='refunded' AND {sale_day} BETWEEN ? AND ?
            """, (start, end))
            metrics["refunds"] = float((cursor.fetchone() or (0,))[0] or 0)
            metrics["net_sales"] = metrics["gross_sales"] - metrics["discounts"] - metrics["refunds"]

            cursor.execute(f"""
                SELECT COALESCE(SUM(p.cost * si.qty), 0)
                FROM sale_items si
                JOIN products p ON si.product_id=p.id OR (si.product_id IS NULL AND si.product_name=p.name)
                JOIN sales s ON si.sale_id=s.id
                WHERE s.status='completed' AND {sale_day} BETWEEN ? AND ?
                  AND (p.sold_by IS NULL OR p.sold_by!='Service')
            """, (start, end))
            metrics["cogs"] = float((cursor.fetchone() or (0,))[0] or 0)
            metrics["gross_profit"] = metrics["net_sales"] - metrics["cogs"]

            cursor.execute(f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE {expense_day} BETWEEN ? AND ?", (start, end))
            metrics["expenses"] = float((cursor.fetchone() or (0,))[0] or 0)
            metrics["net_profit"] = metrics["gross_profit"] - metrics["expenses"]

            cursor.execute("""SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by!='Service') AND stock>0 AND stock<=low_stock""")
            metrics["low_stock"] = int((cursor.fetchone() or (0,))[0] or 0)
            cursor.execute("""SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by!='Service') AND stock<=0""")
            metrics["out_of_stock"] = int((cursor.fetchone() or (0,))[0] or 0)

            if "credit" in permissions and table_exists(cursor, "customers") and table_exists(cursor, "credit_sales"):
                cursor.execute("""
                    WITH customer_debt AS (
                        SELECT COALESCE(c.current_balance,0) current_balance,
                               COALESCE((SELECT SUM(cs.balance_amount) FROM credit_sales cs
                                 WHERE cs.customer_id=c.id AND cs.balance_amount>0
                                   AND LOWER(COALESCE(cs.status,''))!='refunded'),0) credit_sales_balance
                        FROM customers c
                    )
                    SELECT COALESCE(SUM(CASE WHEN current_balance>credit_sales_balance
                                      THEN current_balance ELSE credit_sales_balance END),0)
                    FROM customer_debt
                """)
                metrics["outstanding_credit"] = float((cursor.fetchone() or (0,))[0] or 0)

            if "cash_sessions" in permissions and table_exists(cursor, "cash_sessions"):
                cursor.execute("SELECT COUNT(*) FROM cash_sessions WHERE LOWER(COALESCE(status,''))='open'")
                metrics["open_cash_sessions"] = int((cursor.fetchone() or (0,))[0] or 0)

            if "attendance" in permissions and table_exists(cursor, "attendance"):
                cursor.execute(f"""SELECT COUNT(*),COALESCE(SUM(CASE WHEN LOWER(COALESCE(status,''))
                    IN ('late','incomplete','absent','half-day') THEN 1 ELSE 0 END),0) FROM attendance
                    WHERE {attendance_day} BETWEEN ? AND ?""", (start, end))
                attendance=cursor.fetchone() or (0,0);metrics["attendance_records"]=int(attendance[0] or 0);metrics["attendance_issues"]=int(attendance[1] or 0)
            return metrics
        finally:
            conn.close()

    @staticmethod
    def _rows(metrics):
        labels = {
            "gross_sales": "Gross Sales", "discounts": "Discounts", "refunds": "Refunds",
            "net_sales": "Net Sales", "transactions": "Transactions", "cogs": "COGS",
            "gross_profit": "Gross Profit", "expenses": "Expenses", "net_profit": "Net Profit",
            "outstanding_credit": "Outstanding Credit", "low_stock": "Low Stock",
            "out_of_stock": "Out of Stock", "open_cash_sessions": "Open Cash Sessions",
            "attendance_issues": "Attendance Issues",
            "attendance_records": "Attendance Records",
        }
        return [{"Metric": labels[key], "Value": value} for key, value in metrics.items() if value is not None]

    @staticmethod
    def _message(metrics, start, end):
        money = lambda value: f"{float(value or 0):,.0f} Ks"
        lines = [
            f"📊 **Dashboard Summary — {start} to {end}**", "",
            f"• Gross sales: {money(metrics['gross_sales'])}",
            f"• Discounts: {money(metrics['discounts'])}",
            f"• Refunds: {money(metrics['refunds'])}",
            f"• Net sales: {money(metrics['net_sales'])}",
            f"• Transactions: {metrics['transactions']}",
            f"• Gross profit: {money(metrics['gross_profit'])}",
            f"• Expenses: {money(metrics['expenses'])}",
            f"• Net profit: {money(metrics['net_profit'])}",
            f"• Low stock / Out of stock: {metrics['low_stock']} / {metrics['out_of_stock']}",
        ]
        if metrics["outstanding_credit"] is not None:
            lines.append(f"• Outstanding credit: {money(metrics['outstanding_credit'])}")
        if metrics["open_cash_sessions"] is not None:
            lines.append(f"• Open cash sessions: {metrics['open_cash_sessions']}")
        if metrics["attendance_issues"] is not None:
            lines.append(f"• Attendance issues: {metrics['attendance_issues']}")
        lines.extend(["", "Values are read-only and use the selected Dashboard period. Restricted metrics are omitted when permission is unavailable."])
        return "\n".join(lines)

    @staticmethod
    def _result(message, data, start, end, metrics=None):
        return {
            "type": "dashboard_summary", "message": message, "data": data, "sql": "",
            "start_date": start, "end_date": end, "metrics": metrics or {},
            "_required_permissions": ["dashboard"],
        }

    @staticmethod
    def _comparison_result(message, data, current_start, current_end, previous_start, previous_end, current=None, previous=None, changes=None):
        return {
            "type": "dashboard_comparison", "message": message, "data": data, "sql": "",
            "start_date": current_start, "end_date": current_end,
            "previous_start_date": previous_start, "previous_end_date": previous_end,
            "metrics": current or {}, "previous_metrics": previous or {}, "changes": changes or {},
            "_required_permissions": ["dashboard"],
        }

    @staticmethod
    def _chart_result(message, data, kind, start, end):
        return {
            "type": "dashboard_chart", "message": message, "data": data, "sql": "",
            "chart_kind": kind, "start_date": start, "end_date": end,
            "_required_permissions": ["dashboard"],
        }

    @staticmethod
    def _alert_result(message,data,start,end,previous_start,previous_end,current=None,previous=None):
        return {"type":"dashboard_alerts","message":message,"data":data,"sql":"","start_date":start,"end_date":end,
                "previous_start_date":previous_start,"previous_end_date":previous_end,"metrics":current or {},"previous_metrics":previous or {},
                "_required_permissions":["dashboard"]}

    @staticmethod
    def _explanation_result(message,data,focus,start,end,previous_start,previous_end):
        required=["dashboard"]+(["sales_summary"] if focus=="sales" else ["expense"] if focus=="expenses" else ["sales_summary","expense"])
        return {"type":"dashboard_explanation","message":message,"data":data,"sql":"","explanation_focus":focus,
                "start_date":start,"end_date":end,"previous_start_date":previous_start,"previous_end_date":previous_end,
                "_required_permissions":required}
