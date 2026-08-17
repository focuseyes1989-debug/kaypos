"""Guarded natural-language planning for approved, read-only insights."""

import re
from collections import defaultdict
from datetime import date, timedelta

from models.database import connect_db
from services import employee_service
from ui.ai_pages.ai_employee_queries import EmployeeQueryHandler
from utils.db_compat import is_postgres_backend
from utils.permissions import PermissionManager


class AINaturalLanguagePlanner:
    @classmethod
    def plan(cls,query):
        text=(query or "").lower().strip()
        if cls._raw_sql(text):return {"intent":"blocked_action","confidence":1.0,"reason":"Raw SQL is not accepted in AI Chat."}
        if cls._write_action(text):return {"intent":"blocked_action","confidence":1.0,"reason":"This request could change business data and is not available through the read-only intelligence layer."}
        attendance=any(word in text for word in ("attendance","တက်ရောက်","အလုပ်တက်","အလုပ်ဝင်","နောက်ကျ","အလုပ်ပျက်"))
        sales=any(word in text for word in ("sales","sale","revenue","အရောင်း","ရောင်းအား"))
        if attendance and sales and any(word in text for word in ("but","however","compare","relationship","ပေမယ့်","နှိုင်း","ဆက်စပ်")):
            return {"intent":"sales_attendance_correlation","confidence":0.94}
        if attendance and any(word in text for word in ("most late","latest arrival","top late","နောက်ကျဆုံး","အနောက်ကျဆုံး","ဘယ်သူနောက်ကျ")):
            return {"intent":"late_ranking","confidence":0.96,"limit":cls._limit(text,3)}
        if attendance and any(word in text for word in ("health","condition","good","bad","overview","အခြေအနေ","ကောင်းလား","မကောင်း")):
            return {"intent":"attendance_health","confidence":0.93}
        if any(word in text for word in ("business","shop","လုပ်ငန်း","ဆိုင်")) and any(word in text for word in ("health","condition","overview","summary","အခြေအနေ","အကျဉ်းချုပ်","ကောင်းလား")):
            return {"intent":"business_health","confidence":0.92}
        if text in ("အခြေအနေဘယ်လိုလဲ","အခြေအနေကရော","show insights","give me insights"):
            return {"intent":"clarification","confidence":0.45}
        return None

    @staticmethod
    def _raw_sql(text):
        return bool(re.search(r"(?:^|\s)(select|insert|update|delete|drop|alter|truncate|create)\s+(?:\*|from|into|table|[a-z_])",text,re.I))

    @staticmethod
    def _write_action(text):
        english=bool(re.search(r"\b(delete|remove|drop|truncate|update|insert|refund|mark\s+paid|pay\s+payroll|adjust\s+stock|change\s+salary|set\s+salary)\b",text,re.I))
        myanmar=any(phrase in text for phrase in ("ဖျက်ပေး","ပြင်ပေး","ပြောင်းပေး","refund လုပ်","paid လုပ်","ငွေပေးချေ","စတော့ညှိ"))
        return english or myanmar

    @staticmethod
    def _limit(text,default):
        match=re.search(r"\b(\d{1,2})\b",text)
        if match:return min(20,max(1,int(match.group(1))))
        for word,value in (("တစ်",1),("နှစ်",2),("သုံး",3),("လေး",4),("ငါး",5),("ဆယ်",10)):
            if word in text:return value
        return default


class AIInsightHandler:
    REQUIRED={"attendance_health":{"attendance"},"late_ranking":{"attendance"},"sales_attendance_correlation":{"attendance","employee_performance"},"business_health":{"sales_summary","expense"}}

    @classmethod
    def handle(cls,plan,query,user_id):
        intent=plan.get("intent")
        if intent=="blocked_action":return cls._result("🛡️ **Read-only guard**\n\n"+plan["reason"]+"\n\nOpen the relevant page and use its confirmation workflow for authorized changes.",[],intent,set())
        if intent=="clarification":return cls._result("❓ **Please choose an area**\n\n• Business overview\n• Employee attendance health\n• Late employee ranking\n• Sales and attendance comparison",[],intent,set())
        required=cls.REQUIRED.get(intent,set());permissions=cls._permissions(user_id)
        # Reports is allowed to satisfy the sales-summary side of business health.
        missing=set(required)
        if "sales_summary" in missing and ({"sales_summary","reports"}&permissions):missing.remove("sales_summary")
        missing-=permissions
        if missing:return cls._result("🔒 This insight requires: "+", ".join(sorted(missing))+".",[],intent,required)
        if intent=="attendance_health":return cls._attendance_health(query,required)
        if intent=="late_ranking":return cls._late_ranking(query,plan.get("limit",3),required)
        if intent=="sales_attendance_correlation":return cls._correlation(query,required)
        if intent=="business_health":return cls._business_health(query,required)
        return None

    @staticmethod
    def _permissions(user_id):
        try:return PermissionManager.get_user_permissions(int(user_id))
        except (TypeError,ValueError):return set()

    @classmethod
    def _range(cls,query):
        text=(query or "").lower()
        has_period=bool(re.search(r"\b20\d{2}(?:-\d{2})?(?:-\d{2})?\b",text)) or any(word in text for word in ("today","yesterday","this month","last month","ဒီနေ့","မနေ့က","ဒီလ","ပြီးခဲ့တဲ့လ"))
        return EmployeeQueryHandler._date_range(query if has_period else f"{query} this month")

    @classmethod
    def _attendance_health(cls,query,required):
        start,end=cls._range(query);rows=employee_service.list_attendance(start,end)
        counts={status:sum(str(row.get("status") or "").lower()==status.lower() for row in rows) for status in ("Present","Late","Incomplete","Absent","Half-day","Leave")}
        working=max(0,len(rows)-counts["Leave"]);issues=counts["Late"]+counts["Incomplete"]+counts["Absent"]+counts["Half-day"]
        issue_rate=(issues/working*100) if working else 0
        rating="Healthy" if working and issue_rate<=10 else "Attention" if working and issue_rate<=25 else "Needs action" if working else "No attendance data"
        data=[{"Metric":"Records","Value":len(rows)},{"Metric":"Present","Value":counts["Present"]},{"Metric":"Late","Value":counts["Late"]},{"Metric":"Incomplete","Value":counts["Incomplete"]},{"Metric":"Absent","Value":counts["Absent"]},{"Metric":"Half-day","Value":counts["Half-day"]},{"Metric":"Leave","Value":counts["Leave"]},{"Metric":"Issue Rate %","Value":round(issue_rate,1)}]
        message=(f"🧠 **Attendance Health — {start} to {end}**\n\nRating: **{rating}**\nIssue rate: {issue_rate:.1f}%\n\n"
                 f"• Present: {counts['Present']}\n• Late: {counts['Late']}\n• Incomplete: {counts['Incomplete']}\n• Absent: {counts['Absent']}\n• Half-day: {counts['Half-day']}\n• Leave: {counts['Leave']}\n\n"
                 "Rating rule: Healthy ≤10%, Attention ≤25%, Needs action >25%. This is an operational indicator, not an employee evaluation.")
        return cls._result(message,data,"attendance_health",required)

    @classmethod
    def _late_ranking(cls,query,limit,required):
        start,end=cls._range(query);rows=employee_service.list_attendance(start,end);grouped=defaultdict(lambda:{"late_days":0,"late_minutes":0,"full_name":""})
        for row in rows:
            minutes=int(row.get("late_minutes") or 0)
            if str(row.get("status"))!="Late" and minutes<=0:continue
            key=row.get("employee_no") or str(row.get("employee_id"));grouped[key]["employee_no"]=row.get("employee_no");grouped[key]["full_name"]=row.get("full_name") or key;grouped[key]["late_days"]+=1;grouped[key]["late_minutes"]+=minutes
        data=sorted(grouped.values(),key=lambda item:(item["late_minutes"],item["late_days"]),reverse=True)[:limit]
        message=f"⏰ **Most Late Employees — {start} to {end}**\n\n"
        message+=("\n".join(f"{index}. {row['employee_no']} — {row['full_name']}: {row['late_days']} day(s), {row['late_minutes']} minute(s)" for index,row in enumerate(data,1)) if data else "No late attendance records found.")
        return cls._result(message,data,"late_ranking",required)

    @classmethod
    def _correlation(cls,query,required):
        start,end=cls._range(query);performance=employee_service.performance_report(start,end);attendance=employee_service.list_attendance(start,end);issues=defaultdict(int)
        for row in attendance:
            if str(row.get("status")) in ("Late","Incomplete","Absent","Half-day"):issues[row.get("employee_no")]+=1
        data=[]
        for row in performance:
            if float(row.get("sales_total") or 0)>0 and issues.get(row.get("employee_no"),0)>0:
                data.append({"employee_no":row.get("employee_no"),"full_name":row.get("full_name"),"sales_total":float(row.get("sales_total") or 0),"sale_count":int(row.get("sale_count") or 0),"attendance_issues":issues[row.get("employee_no")]})
        data.sort(key=lambda item:item["sales_total"],reverse=True)
        message=f"🔎 **Sales + Attendance Review — {start} to {end}**\n\n"
        message+=("\n".join(f"• {row['employee_no']} — {row['full_name']}: Sales {row['sales_total']:,.0f} Ks, Attendance issues {row['attendance_issues']}" for row in data[:20]) if data else "No employee had both recorded sales and attendance issues in this period.")
        message+="\n\nThis is a side-by-side operational comparison; it does not prove that attendance caused sales performance."
        return cls._result(message,data,"sales_attendance_correlation",required)

    @classmethod
    def _business_health(cls,query,required):
        start,end=cls._range(query);current=cls._business_period(start,end)
        days=(date.fromisoformat(end)-date.fromisoformat(start)).days+1;previous_end=date.fromisoformat(start)-timedelta(days=1);previous_start=previous_end-timedelta(days=days-1);previous=cls._business_period(previous_start.isoformat(),previous_end.isoformat())
        change=((current["sales"]-previous["sales"])/previous["sales"]*100) if previous["sales"] else None
        rating="Positive" if current["net"]>=0 and current["sales"]>0 else "Needs attention" if current["sales"] else "No sales data"
        data=[{"Period":f"{start} to {end}",**current},{"Period":f"{previous_start} to {previous_end}",**previous}]
        change_text=f"{change:+.1f}%" if change is not None else "No comparable prior sales"
        message=(f"🏪 **Business Health — {start} to {end}**\n\nRating: **{rating}**\nSales change: {change_text}\n\n"
                 f"• Transactions: {current['transactions']}\n• Sales: {current['sales']:,.0f} Ks\n• Gross profit: {current['gross_profit']:,.0f} Ks\n• Expenses: {current['expenses']:,.0f} Ks\n• Net after expenses: {current['net']:,.0f} Ks\n\n"
                 "The rating is based only on recorded sales, gross profit and expenses for the selected period.")
        return cls._result(message,data,"business_health",required)

    @staticmethod
    def _business_period(start,end):
        conn=connect_db();cur=conn.cursor()
        date_sales="CAST(created_at AS DATE)" if is_postgres_backend() else "date(created_at)"
        date_expense="CAST(NULLIF(expense_date,'') AS DATE)" if is_postgres_backend() else "date(expense_date)"
        try:
            cur.execute(f"SELECT COUNT(*),COALESCE(SUM(total),0),COALESCE(SUM(gross_profit),0) FROM sales WHERE {date_sales} BETWEEN ? AND ? AND status='completed'",(start,end));sales=cur.fetchone() or (0,0,0)
            cur.execute(f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE {date_expense} BETWEEN ? AND ?",(start,end));expenses=float((cur.fetchone() or (0,))[0] or 0)
            gross=float(sales[2] or 0);return {"transactions":int(sales[0] or 0),"sales":float(sales[1] or 0),"gross_profit":gross,"expenses":expenses,"net":gross-expenses}
        finally:conn.close()

    @staticmethod
    def _result(message,data,intent,required):
        return {"type":"insight","data":data,"message":message,"sql":"","insight_kind":intent,"_required_permissions":sorted(required)}
