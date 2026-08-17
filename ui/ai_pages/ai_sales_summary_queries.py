"""Phase 1: permission-aware Sales Summary questions for AI Chat."""

import re
from datetime import date,timedelta

from models.database import connect_db
from ui.ai_pages.ai_employee_queries import EmployeeQueryHandler
from ui.ai_pages.ai_dashboard_queries import AIDashboardQueryHandler
from utils.db_compat import is_postgres_backend
from utils.permissions import PermissionManager


class AISalesSummaryQueryHandler:
    """Use the Sales Summary page definitions for deterministic read-only totals."""

    @staticmethod
    def handles(query):
        text=(query or "").lower()
        summary_terms=("sales summary","sale summary","sales overview","sales report","အရောင်းအကျဉ်းချုပ်","ရောင်းအားအကျဉ်းချုပ်","အရောင်း စာရင်းချုပ်","ရောင်းအား စာရင်းချုပ်")
        sales_terms=("sales","sale","အရောင်း","ရောင်းအား")
        metric_terms=("gross","net","transaction","order","items sold","average sale","average order","discount","refund","compare","comparison"," vs ","why","reason","explain","recommend","suggest","what should","ဘာကြောင့်","ဘာကြောင့်","ဘာလို့","အကြောင်းရင်း","ဘာလုပ်သင့်","အကြံပြု","alert","warning","anomaly","unusual","risk","ပုံမှန်မဟုတ်","သတိထား","သတိပေး","chart","graph","trend","daily","hourly","by hour","top","best","highest","lowest","low-selling","product","item","category","payment","cash","cashier","employee performance","sales performance","kpay","wavepay","bank","credit","mixed","စုစုပေါင်း","အသားတင်","ဘယ်နှခု","ပျမ်းမျှ","လျှော့စျေး","လျော့စျေး","ပြန်အမ်း","နှိုင်း","တိုးလား","လျော့လား","အကောင်းဆုံး","အများဆုံး","အနည်းဆုံး","မရောင်းရဆုံး","ပစ္စည်း","အမျိုးအစား","ငွေပေးချေ","ငွေချေ","ငွေသား","ဝန်ထမ်း","ဂရပ်","နေ့အလိုက်","နာရီအလိုက်")
        direct_terms=("transaction ဘယ်နှခု","transaction ဘယ်လောက်","order ဘယ်နှခု","ပစ္စည်းဘယ်နှခုရောင်း","ပစ္စည်း ဘယ်နှခု ရောင်း")
        return any(term in text for term in summary_terms) or (any(term in text for term in sales_terms) and any(term in text for term in metric_terms)) or any(term in text for term in direct_terms) or AISalesSummaryQueryHandler._analysis_kind(text) is not None

    @staticmethod
    def _permissions(user_id):
        try:return PermissionManager.get_user_permissions(int(user_id)) or set()
        except (TypeError,ValueError):return set()

    @classmethod
    def handle(cls,query,user_id):
        if not cls.handles(query):return None
        permissions=cls._permissions(user_id)
        if cls._is_alert(query):
            if not ({"sales_summary","reports"}&set(permissions)):return cls._alert_result("🔒 Sales Summary permission is required for sales alerts.",[],None,None,None,None)
            return cls._alerts(query,permissions)
        if cls._is_explanation(query):
            if not ({"sales_summary","reports"}&set(permissions)):return cls._explanation_result("🔒 Sales Summary permission is required for change explanations.",[],[],None,None,None,None)
            return cls._explain(query,permissions)
        analysis_kind=cls._analysis_kind(query)
        if analysis_kind=="cashiers":
            company_allowed={"sales_summary","employee_performance"}<=set(permissions)
            personal=cls._wants_personal(query) or ("sales" in permissions and not company_allowed)
            if personal and "sales" not in permissions:return cls._breakdown_result("🔒 Sales permission is required for personal performance.",[],"cashiers",None,None)
            if not personal and not company_allowed:return cls._breakdown_result("🔒 Sales Summary and Employee Performance permissions are required.",[],"cashiers",None,None)
            start,end=EmployeeQueryHandler._date_range(query);return cls._cashier_analysis(query,start,end,user_id,personal)
        if not ({"sales_summary","reports"}&set(permissions)):
            return cls._result("🔒 Sales Summary permission is required.",{},None,None)
        if analysis_kind=="payments":
            start,end=EmployeeQueryHandler._date_range(query)
            return cls._analysis(query,start,end,analysis_kind)
        if cls._is_comparison(query):return cls._comparison(query)
        start,end=EmployeeQueryHandler._date_range(query)
        if analysis_kind in ("daily_sales","hourly_sales"):return cls._trend_analysis(start,end,analysis_kind)
        if analysis_kind:return cls._analysis(query,start,end,analysis_kind)
        try:metrics=cls.collect(start,end)
        except Exception as exc:return cls._result(f"❌ Sales Summary failed: {exc}",{},start,end)
        return cls._result(cls._message(metrics,start,end),metrics,start,end)

    @staticmethod
    def _analysis_kind(query):
        text=(query or "").lower()
        if any(term in text for term in ("hourly","by hour","hour pattern","နာရီအလိုက်","ဘယ်အချိန်")):return "hourly_sales"
        if any(term in text for term in ("cashier","sales performance","employee sales","ဝန်ထမ်းအရောင်း","ဝန်ထမ်း အရောင်း","အရောင်းအကောင်းဆုံး ဝန်ထမ်း","အရောင်းအကောင်းဆုံး cashier","ရဲ့ အရောင်း","ကိုယ်ပိုင်အရောင်း performance")) or ("emp-" in text and any(term in text for term in ("sales","အရောင်း"))):return "cashiers"
        if any(term in text for term in ("payment","cash","kpay","wavepay","wave pay","bank","credit","mixed","ငွေပေးချေ","ငွေချေ","ငွေသား")):return "payments"
        if any(term in text for term in ("category","categories","အမျိုးအစား","ကဏ္ဍ")):return "categories"
        if any(term in text for term in ("lowest","low-selling","worst selling","မရောင်းရဆုံး","အနည်းဆုံး")) and any(term in text for term in ("product","item","ပစ္စည်း")):return "low_products"
        if any(term in text for term in ("top","best","highest","အကောင်းဆုံး","အများဆုံး")) and any(term in text for term in ("product","item","ပစ္စည်း")):return "top_products"
        if any(term in text for term in ("chart","graph","trend","daily sales","နေ့အလိုက်","ဂရပ်")) and any(term in text for term in ("sales","sale","အရောင်း","ရောင်းအား")):return "daily_sales"
        return None

    @classmethod
    def _trend_analysis(cls,start,end,kind):
        try:data,actual_start,actual_end=cls.collect_trend(kind,start,end)
        except Exception as exc:return cls._chart_result(f"❌ Sales chart failed: {exc}",[],kind,start,end)
        title="Hourly Sales Pattern" if kind=="hourly_sales" else "Daily Sales Trend"
        if not data:return cls._chart_result(f"🔍 No sales trend data found for {actual_start} to {actual_end}.",[],kind,actual_start,actual_end)
        total=sum(float(row.get("Sales") or 0) for row in data);transactions=sum(int(row.get("Transactions") or 0) for row in data)
        return cls._chart_result(f"📉 **{title} — {actual_start} to {actual_end}**\n\n{len(data)} point(s), {transactions} transactions, {total:,.0f} Ks total sales.",data,kind,actual_start,actual_end)

    @staticmethod
    def collect_trend(kind,start,end):
        start_day,end_day=date.fromisoformat(start),date.fromisoformat(end)
        if kind=="daily_sales" and (end_day-start_day).days>30:start_day=end_day-timedelta(days=30)
        start,end=start_day.isoformat(),end_day.isoformat();conn=connect_db();cursor=conn.cursor()
        try:
            if kind=="hourly_sales":
                bucket="CAST(EXTRACT(HOUR FROM created_at) AS INTEGER)" if is_postgres_backend() else "CAST(strftime('%H',created_at) AS INTEGER)";day="CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
                cursor.execute(f"SELECT {bucket},COALESCE(SUM(total),0),COUNT(*) FROM sales WHERE status='completed' AND {day} BETWEEN ? AND ? GROUP BY {bucket} ORDER BY {bucket}",(start,end));rows=cursor.fetchall()
                return [{"Hour":f"{int(row[0]):02d}:00","Sales":float(row[1] or 0),"Transactions":int(row[2] or 0)} for row in rows],start,end
            bucket="CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
            cursor.execute(f"SELECT {bucket},COALESCE(SUM(total),0),COUNT(*) FROM sales WHERE status='completed' AND {bucket} BETWEEN ? AND ? GROUP BY {bucket} ORDER BY {bucket}",(start,end));rows=cursor.fetchall()
            return [{"Date":str(row[0]),"Sales":float(row[1] or 0),"Transactions":int(row[2] or 0)} for row in rows],start,end
        finally:conn.close()

    @staticmethod
    def _wants_personal(query):
        text=(query or "").lower()
        return any(term in text for term in ("my sales","my performance","personal sales","ကိုယ်ပိုင်အရောင်း","ကျွန်တော့်အရောင်း","ကျွန်တော့်အရောင်း","ကျွန်မအရောင်း"))

    @classmethod
    def _cashier_analysis(cls,query,start,end,user_id,personal=False):
        context=AIDashboardQueryHandler._user_context(user_id) if personal else {};username=context.get("username") if personal else None
        if personal and not username:return cls._breakdown_result("🔍 The logged-in user is not mapped to a sales account.",[],"cashiers",start,end)
        try:rows=cls.collect_cashiers(start,end,username)
        except Exception as exc:return cls._breakdown_result(f"❌ Cashier performance failed: {exc}",[],"cashiers",start,end)
        if not personal:
            matches=[row for row in rows if cls._employee_matches(query,row)]
            if matches:rows=matches
            else:rows=rows[:cls._cashier_limit(query,len(rows))]
        if not rows:return cls._breakdown_result(f"🔍 No cashier sales found for {start} to {end}.",[],"cashiers",start,end)
        lines=[f"👥 **{'My Sales Performance' if personal else 'Cashier Sales Performance'} — {start} to {end}**",""]
        for row in rows:lines.append(f"{row['Rank']}. {row['Employee']}: {row['Sales']:,.0f} Ks ({row['Transactions']} sales, {row['Items Sold']:,.2f} items, avg {row['Average Sale']:,.0f} Ks, discount {row['Discounts']:,.0f} Ks, refund {row['Refunds']:,.0f} Ks)")
        result=cls._breakdown_result("\n".join(lines),rows,"cashiers",start,end,sum(row["Sales"] for row in rows));result.update({"scope":"personal" if personal else "business","scope_label":context.get("full_name") or username if personal else "All authorized cashiers"});return result

    @staticmethod
    def _cashier_limit(query,default=10):
        match=re.search(r"(?:top|first|အကောင်းဆုံး)?\s*(\d{1,2})\s*(?:cashiers?|employees?|ဝန်ထမ်း|ယောက်)",query or "",re.IGNORECASE)
        return max(1,min(50,int(match.group(1)))) if match else default

    @staticmethod
    def _employee_matches(query,row):
        text=(query or "").lower()
        return any(str(row.get(key) or "").lower() in text for key in ("Employee No","Employee","Username") if row.get(key))

    @staticmethod
    def collect_cashiers(start,end,username=None):
        conn=connect_db();cursor=conn.cursor();day="CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)";item_day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
        try:
            where=" AND created_by=?" if username else "";item_where=" AND s.created_by=?" if username else "";params=[start,end]+([username] if username else [])
            cursor.execute(f"""WITH sale_stats AS (
                    SELECT created_by,COUNT(CASE WHEN status='completed' THEN 1 END) AS transactions,
                           COALESCE(SUM(CASE WHEN status='completed' THEN total ELSE 0 END),0) AS sales,
                           COALESCE(SUM(CASE WHEN status='completed' THEN discount_amount ELSE 0 END),0) AS discounts,
                           COALESCE(SUM(CASE WHEN status='refunded' THEN total ELSE 0 END),0) AS refunds
                    FROM sales WHERE {day} BETWEEN ? AND ?{where} GROUP BY created_by),
                item_stats AS (
                    SELECT s.created_by,COALESCE(SUM(si.qty),0) AS items_sold FROM sales s JOIN sale_items si ON si.sale_id=s.id
                    WHERE s.status='completed' AND {item_day} BETWEEN ? AND ?{item_where} GROUP BY s.created_by)
                SELECT ss.created_by,e.employee_no,COALESCE(e.full_name,ss.created_by),ss.transactions,ss.sales,COALESCE(it.items_sold,0),ss.discounts,ss.refunds
                FROM sale_stats ss LEFT JOIN users u ON u.username=ss.created_by LEFT JOIN employees e ON e.user_id=u.id LEFT JOIN item_stats it ON it.created_by=ss.created_by
                ORDER BY ss.sales DESC""",params+params)
            raw=cursor.fetchall();rows=[]
            for rank,row in enumerate(raw,1):
                transactions=int(row[3] or 0);sales=float(row[4] or 0)
                rows.append({"Rank":rank,"Username":row[0],"Employee No":row[1],"Employee":row[2],"Transactions":transactions,"Sales":sales,"Items Sold":float(row[5] or 0),"Average Sale":sales/transactions if transactions else 0.0,"Discounts":float(row[6] or 0),"Refunds":float(row[7] or 0)})
            return rows
        finally:conn.close()

    @staticmethod
    def _limit(query,default=10):
        text=re.sub(r"20\d{2}-\d{1,2}-\d{1,2}"," ",query or "")
        match=re.search(r"(?:top|first|အကောင်းဆုံး)?\s*(\d{1,2})\s*(?:products?|items?|မျိုး|ခု|ပစ္စည်း)",text,re.IGNORECASE)
        return max(1,min(50,int(match.group(1)))) if match else default

    @classmethod
    def _analysis(cls,query,start,end,kind):
        limit=cls._limit(query)
        try:
            rows=cls.collect_breakdown(kind,start,end,limit)
            overall_total=sum(float(row.get("Revenue") or 0) for row in rows)
            for row in rows:row["Share %"]=round(float(row.get("Revenue") or 0)/overall_total*100,1) if overall_total else 0.0
            if kind=="categories":
                requested=cls._requested_category(query,rows)
                if requested:rows=[row for row in rows if str(row["Label"]).lower()==requested.lower()]
            elif kind=="payments":
                requested=cls._requested_payments(query,rows)
                if requested:rows=[row for row in rows if str(row["Label"]).lower() in requested]
            total=sum(float(row.get("Revenue") or 0) for row in rows)
        except Exception as exc:return cls._breakdown_result(f"❌ Sales analysis failed: {exc}",[],kind,start,end)
        title={"top_products":"Top-selling Products","low_products":"Low-selling Products","categories":"Sales by Category","payments":"Sales by Payment Type"}[kind]
        if not rows:return cls._breakdown_result(f"🔍 No {title.lower()} data found for {start} to {end}.",[],kind,start,end)
        lines=[f"📦 **{title} — {start} to {end}**",""]
        for index,row in enumerate(rows,1):
            detail=f"{int(row['Transactions'])} transactions" if kind=="payments" else f"{float(row['Quantity']):,.2f} items"
            lines.append(f"{index}. {row['Label']}: {float(row['Revenue']):,.0f} Ks ({detail}, {row['Share %']:.1f}%)")
        lines.extend(["",f"Total shown revenue: {total:,.0f} Ks"])
        return cls._breakdown_result("\n".join(lines),rows,kind,start,end,total)

    @staticmethod
    def _requested_category(query,rows):
        text=(query or "").lower()
        return next((str(row["Label"]) for row in rows if str(row["Label"]).lower() in text),None)

    @staticmethod
    def _requested_payments(query,rows):
        text=(query or "").lower()
        compact=lambda value:re.sub(r"[\s_-]+","",str(value or "").lower())
        compact_text=compact(text);requested={str(row["Label"]).lower() for row in rows if compact(row["Label"]) in compact_text}
        aliases={"ငွေသား":"cash","အကြွေး":"credit","ဘဏ်":"bank"}
        for word,target in aliases.items():
            if word in text:
                requested.update(str(row["Label"]).lower() for row in rows if target in str(row["Label"]).lower())
        return requested

    @staticmethod
    def collect_breakdown(kind,start,end,limit=10):
        conn=connect_db();cursor=conn.cursor();day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
        try:
            if kind=="payments":
                cursor.execute(f"""SELECT COALESCE(NULLIF(TRIM(s.payment_type),''),'Other'),COUNT(*),COALESCE(SUM(s.total),0)
                    FROM sales s WHERE s.status='completed' AND {day} BETWEEN ? AND ?
                    GROUP BY COALESCE(NULLIF(TRIM(s.payment_type),''),'Other') ORDER BY 3 DESC""",(start,end))
                return [{"Label":row[0],"Transactions":int(row[1] or 0),"Revenue":float(row[2] or 0)} for row in cursor.fetchall()]
            if kind=="categories":
                cursor.execute(f"""SELECT COALESCE(p.category,'Uncategorized'),COALESCE(SUM(si.qty),0),COALESCE(SUM(si.qty*si.price),0)
                    FROM sale_items si JOIN sales s ON s.id=si.sale_id
                    LEFT JOIN products p ON p.id=si.product_id OR (si.product_id IS NULL AND p.name=si.product_name)
                    WHERE s.status='completed' AND {day} BETWEEN ? AND ?
                    GROUP BY COALESCE(p.category,'Uncategorized') ORDER BY 3 DESC LIMIT ?""",(start,end,limit))
            else:
                direction="ASC" if kind=="low_products" else "DESC"
                cursor.execute(f"""SELECT COALESCE(si.product_name,'Unknown'),COALESCE(SUM(si.qty),0),COALESCE(SUM(si.qty*si.price),0)
                    FROM sale_items si JOIN sales s ON s.id=si.sale_id
                    WHERE s.status='completed' AND {day} BETWEEN ? AND ?
                    GROUP BY COALESCE(si.product_name,'Unknown') ORDER BY 3 {direction} LIMIT ?""",(start,end,limit))
            return [{"Label":row[0],"Quantity":float(row[1] or 0),"Revenue":float(row[2] or 0)} for row in cursor.fetchall()]
        finally:conn.close()

    @staticmethod
    def _is_comparison(query):
        text=(query or "").lower()
        return any(term in text for term in ("compare","comparison"," vs ","versus","နှိုင်း","တိုးလား","လျော့လား","ဘယ်လောက်တိုး","ဘယ်လောက်လျော့"))

    @staticmethod
    def _is_alert(query):
        text=(query or "").lower()
        return any(term in text for term in ("alert","warning","anomaly","unusual","risk","ပုံမှန်မဟုတ်","သတိထား","သတိပေး","ထူးခြား"))

    @staticmethod
    def _is_explanation(query):
        text=(query or "").lower()
        return any(term in text for term in ("why","reason","explain","recommend","suggest","what should","ဘာကြောင့်","ဘာကြောင့်","ဘာလို့","အကြောင်းရင်း","ရှင်းပြ","ဘာလုပ်သင့်","အကြံပြု"))

    @classmethod
    def _explain(cls,query,permissions):
        start,end,previous_start,previous_end=AIDashboardQueryHandler.comparison_periods(query)
        try:
            current=cls.collect(start,end);previous=cls.collect(previous_start,previous_end);rows=[]
            for kind,dimension in (("top_products","Product"),("categories","Category"),("payments","Payment")):
                now=cls.collect_breakdown(kind,start,end,50);before=cls.collect_breakdown(kind,previous_start,previous_end,50)
                rows.extend(cls._dimension_changes(now,before,dimension,"Revenue"))
            if "employee_performance" in permissions:
                now=cls.collect_cashiers(start,end);before=cls.collect_cashiers(previous_start,previous_end)
                rows.extend(cls._dimension_changes(now,before,"Cashier","Sales","Employee"))
            metric_changes=cls.compare_metrics(current,previous)
            for key,label,sign in (("discounts","Discount impact",-1),("refunds","Refund impact",-1),("transactions","Transactions",1),("average_sale","Average Sale",1)):
                row=metric_changes[key];rows.append({"Dimension":"Metric","Segment":label,"Current":row["Current"],"Previous":row["Previous"],"Change":row["Change"],"Impact":row["Change"]*sign})
            rows.sort(key=lambda row:abs(float(row.get("Impact") or 0)),reverse=True);recommendations=cls.recommendations(current,previous,rows)
        except Exception as exc:return cls._explanation_result(f"❌ Sales change explanation failed: {exc}",[],[],start,end,previous_start,previous_end)
        net_change=float(current.get("net_sales") or 0)-float(previous.get("net_sales") or 0)
        lines=[f"🔍 **Sales Change Evidence — {start} to {end}**",f"Compared with {previous_start} to {previous_end}. Net-sales change: {net_change:+,.0f} Ks.","","Strongest evidence signals (dimensions can overlap):"]
        for row in rows[:8]:lines.append(f"• {row['Dimension']} — {row['Segment']}: current {row['Current']:,.0f}, previous {row['Previous']:,.0f}, impact {row['Impact']:+,.0f}")
        lines.extend(["","Suggested actions (recommendations, not verified facts):"]);lines.extend(f"• {item}" for item in recommendations)
        return cls._explanation_result("\n".join(lines),rows[:12],recommendations,start,end,previous_start,previous_end,current,previous)

    @staticmethod
    def _dimension_changes(current,previous,dimension,value_key,label_key="Label"):
        current_map={str(row.get(label_key) or row.get("Label") or "Unknown"):float(row.get(value_key) or 0) for row in current};previous_map={str(row.get(label_key) or row.get("Label") or "Unknown"):float(row.get(value_key) or 0) for row in previous};result=[]
        for label in current_map.keys()|previous_map.keys():
            now=current_map.get(label,0);before=previous_map.get(label,0);change=now-before
            if change:result.append({"Dimension":dimension,"Segment":label,"Current":now,"Previous":before,"Change":change,"Impact":change})
        return result

    @staticmethod
    def recommendations(current,previous,rows):
        suggestions=[];sales=float(current.get("net_sales") or 0);previous_sales=float(previous.get("net_sales") or 0);gross=float(current.get("gross_sales") or 0)
        if sales<previous_sales:
            if float(current.get("transactions") or 0)<float(previous.get("transactions") or 0):suggestions.append("Review traffic and conversion because transaction count decreased.")
            if float(current.get("average_sale") or 0)<float(previous.get("average_sale") or 0):suggestions.append("Test bundles or add-on prompts because average sale decreased.")
            negative=next((row for row in rows if row.get("Dimension")=="Product" and float(row.get("Impact") or 0)<0),None)
            if negative:suggestions.append(f"Check availability, price and placement for {negative['Segment']}, the strongest negative product signal.")
        if gross and float(current.get("discounts") or 0)/gross>=.1:suggestions.append("Review discount authorization and promotion effectiveness.")
        if gross and float(current.get("refunds") or 0)/gross>=.05:suggestions.append("Inspect refunded receipts and recurring product reasons.")
        if not suggestions:suggestions.append("No dominant negative driver was found; continue monitoring the next equal-length period.")
        return suggestions[:5]

    @classmethod
    def _alerts(cls,query,permissions):
        start,end,previous_start,previous_end=AIDashboardQueryHandler.comparison_periods(query)
        try:
            current=cls.collect(start,end);previous=cls.collect(previous_start,previous_end)
            products=cls.collect_breakdown("top_products",start,end,50);previous_products=cls.collect_breakdown("top_products",previous_start,previous_end,50)
            payments=cls.collect_breakdown("payments",start,end,50);evidence=cls.collect_anomaly_evidence(start,end)
            alerts=cls.evaluate_alerts(current,previous,products,previous_products,payments,evidence,"employee_performance" in permissions)
        except Exception as exc:return cls._alert_result(f"❌ Sales alerts failed: {exc}",[],start,end,previous_start,previous_end)
        if alerts:
            message="⚠️ **Sales Alerts — "+start+" to "+end+"**\n\n"+"\n".join(f"• {row['Severity']} — {row['Title']}: {row['Evidence']}" for row in alerts)
        else:message=f"✅ No rule-based Sales Summary alerts were triggered for {start} to {end}."
        return cls._alert_result(message,alerts,start,end,previous_start,previous_end,current,previous)

    @staticmethod
    def collect_anomaly_evidence(start,end):
        conn=connect_db();cursor=conn.cursor();day="CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
        try:
            cursor.execute(f"SELECT invoice_no,total FROM sales WHERE status='completed' AND {day} BETWEEN ? AND ? ORDER BY total DESC LIMIT 1",(start,end));largest=cursor.fetchone()
            cursor.execute(f"SELECT COALESCE(AVG(total),0),COUNT(*) FROM sales WHERE status='completed' AND {day} BETWEEN ? AND ?",(start,end));average=cursor.fetchone() or (0,0)
            cursor.execute(f"""SELECT created_by,COALESCE(SUM(total),0),COALESCE(SUM(discount_amount),0),COUNT(*) FROM sales
                WHERE status='completed' AND {day} BETWEEN ? AND ? GROUP BY created_by ORDER BY 3 DESC LIMIT 1""",(start,end));cashier=cursor.fetchone()
            return {"largest_invoice":largest[0] if largest else None,"largest_sale":float(largest[1] or 0) if largest else 0.0,"average_sale":float(average[0] or 0),"transactions":int(average[1] or 0),"cashier":cashier[0] if cashier else None,"cashier_sales":float(cashier[1] or 0) if cashier else 0.0,"cashier_discounts":float(cashier[2] or 0) if cashier else 0.0,"cashier_transactions":int(cashier[3] or 0) if cashier else 0}
        finally:conn.close()

    @staticmethod
    def evaluate_alerts(current,previous,products,previous_products,payments,evidence,allow_cashier=False):
        alerts=[]
        def add(severity,title,evidence_text,recommendation,target,tab):alerts.append({"Severity":severity,"Title":title,"Evidence":evidence_text,"Recommendation":recommendation,"Target":target,"Tab":tab})
        sales=float(current.get("net_sales") or 0);previous_sales=float(previous.get("net_sales") or 0);gross=float(current.get("gross_sales") or 0)
        if previous_sales>0 and sales==0:add("Critical","No sales",f"No completed sales versus {previous_sales:,.0f} Ks previously.","Confirm store operation and sync status.","sales_summary","items")
        elif previous_sales>0 and (sales-previous_sales)/previous_sales<=-.2:add("Warning","Sales decline",f"Net sales fell {(sales-previous_sales)/previous_sales*100:.1f}%.","Review products, cashiers and payment activity.","sales_summary","items")
        discount_rate=float(current.get("discounts") or 0)/gross*100 if gross else 0
        if discount_rate>=10:add("Critical" if discount_rate>=20 else "Warning","High discount rate",f"Discounts are {discount_rate:.1f}% of gross sales.","Review discounted receipts.","receipts","discounts")
        refund_rate=float(current.get("refunds") or 0)/gross*100 if gross else 0
        if refund_rate>=5:add("Critical" if refund_rate>=10 else "Warning","High refund rate",f"Refunds are {refund_rate:.1f}% of gross sales.","Review refunded receipts.","receipts","refunds")
        previous_map={str(row.get("Label")):float(row.get("Revenue") or 0) for row in previous_products};current_map={str(row.get("Label")):float(row.get("Revenue") or 0) for row in products}
        declines=[]
        for name,before in previous_map.items():
            now=current_map.get(name,0)
            if before>0 and now<before*.5:declines.append((name,(now-before)/before*100))
        if declines:
            name,pct=min(declines,key=lambda item:item[1]);add("Warning","Product sales drop",f"{name} revenue fell {pct:.1f}%.","Review product availability and demand.","sales_summary","top_products")
        payment_total=sum(float(row.get("Revenue") or 0) for row in payments)
        if payment_total and int(current.get("transactions") or 0)>=5:
            top=max(payments,key=lambda row:float(row.get("Revenue") or 0));share=float(top.get("Revenue") or 0)/payment_total*100
            if share>=80:add("Info","Payment concentration",f"{top.get('Label')} represents {share:.1f}% of payment sales.","Confirm this matches normal customer behavior.","sales_summary","payments")
        largest=float(evidence.get("largest_sale") or 0);average=float(evidence.get("average_sale") or 0)
        if evidence.get("transactions",0)>=3 and average>0 and largest>=average*3:add("Warning","Large transaction",f"{evidence.get('largest_invoice') or 'A receipt'} is {largest:,.0f} Ks versus {average:,.0f} Ks average.","Review the receipt details.","receipts","receipts")
        cashier_sales=float(evidence.get("cashier_sales") or 0);cashier_rate=float(evidence.get("cashier_discounts") or 0)/cashier_sales*100 if cashier_sales else 0
        if allow_cashier and evidence.get("cashier_transactions",0)>=3 and cashier_rate>=20:add("Warning","Unusual cashier discounts",f"{evidence.get('cashier') or 'A cashier'} discounts equal {cashier_rate:.1f}% of sales.","Review cashier performance and receipts.","employees","performance")
        order={"Critical":0,"Warning":1,"Info":2};return sorted(alerts,key=lambda row:order[row["Severity"]])

    @classmethod
    def _comparison(cls,query):
        current_start,current_end,previous_start,previous_end=AIDashboardQueryHandler.comparison_periods(query)
        try:current=cls.collect(current_start,current_end);previous=cls.collect(previous_start,previous_end)
        except Exception as exc:return cls._comparison_result(f"❌ Sales Summary comparison failed: {exc}",{},current_start,current_end,previous_start,previous_end)
        changes=cls.compare_metrics(current,previous)
        return cls._comparison_result(cls._comparison_message(changes,current_start,current_end,previous_start,previous_end),changes,current_start,current_end,previous_start,previous_end,current,previous)

    @staticmethod
    def compare_metrics(current,previous):
        labels={"gross_sales":"Gross Sales","net_sales":"Net Sales","transactions":"Transactions","items_sold":"Items Sold","average_sale":"Average Sale","discounts":"Discounts","refunds":"Refunds"};changes={}
        for key,label in labels.items():
            now=float(current.get(key) or 0);before=float(previous.get(key) or 0);delta=now-before
            percentage=(delta/abs(before)*100) if before else (None if now else 0.0)
            changes[key]={"Metric":label,"Current":now,"Previous":before,"Change":delta,"Change %":percentage,"Direction":"up" if delta>0 else "down" if delta<0 else "flat"}
        return changes

    @staticmethod
    def _comparison_message(changes,current_start,current_end,previous_start,previous_end):
        lines=[f"📈 **Sales Summary Comparison — {current_start} to {current_end}**",f"Compared with {previous_start} to {previous_end}.",""]
        for row in changes.values():
            pct="NEW" if row["Change %"] is None else f"{row['Change %']:+.1f}%"
            suffix="" if row["Metric"] in ("Transactions","Items Sold") else " Ks"
            lines.append(f"• {row['Metric']}: {row['Current']:,.0f}{suffix} ({pct})")
        return "\n".join(lines)

    @staticmethod
    def collect(start,end):
        conn=connect_db();cursor=conn.cursor();day="CAST(s.created_at AS DATE)" if is_postgres_backend() else "date(s.created_at)"
        try:
            cursor.execute(f"""SELECT COALESCE(SUM(si.qty*si.price),0),COALESCE(SUM(si.qty),0),COUNT(DISTINCT s.id)
                FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id
                WHERE s.status='completed' AND {day} BETWEEN ? AND ?""",(start,end))
            row=cursor.fetchone() or (0,0,0);gross=float(row[0] or 0);items=float(row[1] or 0);transactions=int(row[2] or 0)
            cursor.execute(f"SELECT COALESCE(SUM(s.discount_amount),0) FROM sales s WHERE s.status='completed' AND {day} BETWEEN ? AND ?",(start,end))
            discounts=float((cursor.fetchone() or (0,))[0] or 0)
            cursor.execute(f"""SELECT COALESCE(SUM(si.qty*si.price),0) FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id
                WHERE s.status='refunded' AND {day} BETWEEN ? AND ?""",(start,end))
            refunds=float((cursor.fetchone() or (0,))[0] or 0);net=gross-discounts
            return {"gross_sales":gross,"net_sales":net,"transactions":transactions,"items_sold":items,"average_sale":net/transactions if transactions else 0.0,"discounts":discounts,"refunds":refunds}
        finally:conn.close()

    @staticmethod
    def _message(metrics,start,end):
        money=lambda value:f"{float(value or 0):,.0f} Ks"
        items=float(metrics.get("items_sold") or 0);items_text=f"{items:,.0f}" if items.is_integer() else f"{items:,.2f}"
        return "\n".join([f"📊 **Sales Summary — {start} to {end}**","",f"• Gross Sales: {money(metrics.get('gross_sales'))}",f"• Net Sales: {money(metrics.get('net_sales'))}",f"• Transactions: {int(metrics.get('transactions') or 0)}",f"• Items Sold: {items_text}",f"• Average Sale: {money(metrics.get('average_sale'))}",f"• Discounts: {money(metrics.get('discounts'))}",f"• Refunds: {money(metrics.get('refunds'))}","","Net Sales follows the Sales Summary page definition: completed gross sales minus discounts. Refunds are shown separately."])

    @staticmethod
    def _result(message,metrics,start,end):
        labels={"gross_sales":"Gross Sales","net_sales":"Net Sales","transactions":"Transactions","items_sold":"Items Sold","average_sale":"Average Sale","discounts":"Discounts","refunds":"Refunds"}
        gross=float(metrics.get("gross_sales") or 0);transactions=int(metrics.get("transactions") or 0)
        widget_meta={"has_sales":transactions>0,"discount_rate":float(metrics.get("discounts") or 0)/gross*100 if gross else 0.0,"refund_rate":float(metrics.get("refunds") or 0)/gross*100 if gross else 0.0,"items_per_transaction":float(metrics.get("items_sold") or 0)/transactions if transactions else 0.0}
        return {"type":"sales_summary_foundation","message":message,"data":[{"Metric":labels[key],"Value":value} for key,value in metrics.items()],"sql":"","metrics":metrics,"widget_meta":widget_meta,"start_date":start,"end_date":end,"_required_permissions":["sales_summary"]}

    @staticmethod
    def _comparison_result(message,changes,start,end,previous_start,previous_end,current=None,previous=None):
        return {"type":"sales_summary_comparison","message":message,"data":list(changes.values()),"sql":"","changes":changes,"metrics":current or {},"previous_metrics":previous or {},"start_date":start,"end_date":end,"previous_start_date":previous_start,"previous_end_date":previous_end,"_required_permissions":["sales_summary"]}

    @staticmethod
    def _breakdown_result(message,data,kind,start,end,total=0.0):
        return {"type":"sales_summary_breakdown","message":message,"data":data,"sql":"","analysis_kind":kind,"total_revenue":total,"start_date":start,"end_date":end,"_required_permissions":["sales_summary"]}

    @staticmethod
    def _chart_result(message,data,kind,start,end):
        return {"type":"sales_summary_chart","message":message,"data":data,"sql":"","chart_kind":kind,"start_date":start,"end_date":end,"_required_permissions":["sales_summary"]}

    @staticmethod
    def _alert_result(message,data,start,end,previous_start,previous_end,current=None,previous=None):
        return {"type":"sales_summary_alerts","message":message,"data":data,"sql":"","start_date":start,"end_date":end,"previous_start_date":previous_start,"previous_end_date":previous_end,"metrics":current or {},"previous_metrics":previous or {},"_required_permissions":["sales_summary"]}

    @staticmethod
    def _explanation_result(message,data,recommendations,start,end,previous_start,previous_end,current=None,previous=None):
        return {"type":"sales_summary_explanation","message":message,"data":data,"sql":"","recommendations":recommendations,"start_date":start,"end_date":end,"previous_start_date":previous_start,"previous_end_date":previous_end,"metrics":current or {},"previous_metrics":previous or {},"_required_permissions":["sales_summary"]}
