"""Local, idempotent executive digests for Dashboard AI."""

import json
from datetime import date, timedelta

from models.database import connect_db
from ui.ai_pages.ai_dashboard_queries import AIDashboardQueryHandler
from utils.db_compat import integer_primary_key_sql
from utils.permissions import PermissionManager


class DashboardDigestService:
    KINDS=("daily","weekly","monthly","alerts")

    @classmethod
    def ensure_schema(cls):
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS ai_dashboard_digests(
                id {integer_primary_key_sql()},digest_kind TEXT NOT NULL,period_start TEXT NOT NULL,period_end TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,created_by INTEGER,message TEXT NOT NULL,payload TEXT NOT NULL,
                UNIQUE(digest_kind,period_start,period_end))""");conn.commit()
        finally:conn.close()

    @classmethod
    def handles(cls,query):
        text=(query or "").lower()
        return any(word in text for word in ("executive summary","executive digest","management report","business review","daily closing","latest digest","alert digest","အုပ်ချုပ်မှုအစီရင်ခံစာ","နေ့စဉ်ပိတ်စာရင်း","အပတ်စဉ်သုံးသပ်ချက်","လစဉ်အစီရင်ခံစာ"))

    @classmethod
    def handle(cls,query,user_id):
        if not cls.handles(query):return None
        permissions=cls._permissions(user_id)
        if "dashboard" not in permissions:return cls._result("🔒 Dashboard permission is required for executive digests.",[],"daily",None,None)
        text=(query or "").lower()
        if "latest" in text or "နောက်ဆုံး" in text:return cls.latest(user_id,permissions)
        kind="alerts" if "alert" in text or "သတိ" in text else "monthly" if "monthly" in text or "လစဉ်" in text else "weekly" if "weekly" in text or "အပတ်စဉ်" in text else "daily"
        start,end=cls.current_period(kind)
        return cls.generate(kind,start,end,user_id,permissions)

    @staticmethod
    def _permissions(user_id):
        try:return PermissionManager.get_user_permissions(int(user_id))
        except (TypeError,ValueError):return set()

    @staticmethod
    def current_period(kind,today=None):
        today=today or date.today()
        if kind=="weekly":return (today-timedelta(days=today.weekday())).isoformat(),today.isoformat()
        if kind=="monthly":return today.replace(day=1).isoformat(),today.isoformat()
        return today.isoformat(),today.isoformat()

    @classmethod
    def generate(cls,kind,start,end,user_id,permissions=None):
        if kind not in cls.KINDS:raise ValueError("Unsupported digest kind")
        permissions=permissions if permissions is not None else cls._permissions(user_id)
        if "dashboard" not in permissions:return cls._result("🔒 Dashboard permission is required for executive digests.",[],kind,start,end)
        cls.ensure_schema();existing=cls._load(kind,start,end,permissions)
        if existing:return existing
        current=AIDashboardQueryHandler.collect(start,end,permissions)
        previous_start,previous_end=cls._previous_period(start,end)
        previous=AIDashboardQueryHandler.collect(previous_start,previous_end,permissions)
        changes=AIDashboardQueryHandler.compare_metrics(current,previous);alerts=AIDashboardQueryHandler.evaluate_alerts(current,previous)
        message=cls._message(kind,start,end,previous_start,previous_end,current,changes,alerts)
        payload={"metrics":current,"previous_metrics":previous,"changes":changes,"alerts":alerts,"previous_start":previous_start,"previous_end":previous_end}
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("INSERT INTO ai_dashboard_digests(digest_kind,period_start,period_end,created_by,message,payload) VALUES(?,?,?,?,?,?)",(kind,start,end,int(user_id) if str(user_id).isdigit() else None,message,json.dumps(payload,ensure_ascii=False,default=str)));conn.commit()
        except Exception:
            conn.rollback();existing=cls._load(kind,start,end,permissions)
            if existing:return existing
            raise
        finally:conn.close()
        return cls._result(message,cls._rows(current,changes,alerts),kind,start,end,payload)

    @classmethod
    def latest(cls,user_id,permissions=None):
        permissions=permissions if permissions is not None else cls._permissions(user_id)
        cls.ensure_schema();conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("SELECT digest_kind,period_start,period_end,message,payload FROM ai_dashboard_digests ORDER BY generated_at DESC,id DESC LIMIT 1");row=cursor.fetchone()
        finally:conn.close()
        if not row:return cls._result("📭 No executive digest has been generated yet.",[],"daily",None,None)
        payload=cls._filter_payload(json.loads(row[4] or "{}"),permissions);message=cls._message(row[0],row[1],row[2],payload.get("previous_start") or "—",payload.get("previous_end") or "—",payload.get("metrics",{}),payload.get("changes",{}),payload.get("alerts",[]))
        return cls._result(message,cls._rows(payload.get("metrics",{}),payload.get("changes",{}),payload.get("alerts",[])),row[0],row[1],row[2],payload)

    @classmethod
    def _load(cls,kind,start,end,permissions):
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("SELECT message,payload FROM ai_dashboard_digests WHERE digest_kind=? AND period_start=? AND period_end=?",(kind,start,end));row=cursor.fetchone()
        finally:conn.close()
        if not row:return None
        payload=cls._filter_payload(json.loads(row[1] or "{}"),permissions);message=cls._message(kind,start,end,payload.get("previous_start") or "—",payload.get("previous_end") or "—",payload.get("metrics",{}),payload.get("changes",{}),payload.get("alerts",[]))
        return cls._result(message,cls._rows(payload.get("metrics",{}),payload.get("changes",{}),payload.get("alerts",[])),kind,start,end,payload)

    @staticmethod
    def _filter_payload(payload,permissions):
        payload=dict(payload or {});permissions=set(permissions or set());metrics=dict(payload.get("metrics") or {});previous=dict(payload.get("previous_metrics") or {});changes=dict(payload.get("changes") or {});alerts=list(payload.get("alerts") or [])
        restrictions={"credit":("outstanding_credit",),"attendance":("attendance_issues","attendance_records"),"cash_sessions":("open_cash_sessions",)}
        for permission,keys in restrictions.items():
            if permission not in permissions:
                for key in keys:metrics.pop(key,None);previous.pop(key,None);changes.pop(key,None)
        def allowed(alert):
            target,tab=alert.get("Target"),alert.get("Tab")
            if target=="customers" and "credit" not in permissions:return False
            if target=="employees" and tab=="attendance" and "attendance" not in permissions:return False
            if target=="employees" and tab=="cash_sessions" and "cash_sessions" not in permissions:return False
            return True
        payload.update({"metrics":metrics,"previous_metrics":previous,"changes":changes,"alerts":[row for row in alerts if allowed(row)]});return payload

    @staticmethod
    def _previous_period(start,end):
        first,last=date.fromisoformat(start),date.fromisoformat(end);days=(last-first).days+1;previous_end=first-timedelta(days=1);return (previous_end-timedelta(days=days-1)).isoformat(),previous_end.isoformat()

    @staticmethod
    def _message(kind,start,end,previous_start,previous_end,metrics,changes,alerts):
        label={"daily":"Daily Closing Summary","weekly":"Weekly Business Review","monthly":"Monthly Management Report","alerts":"Alert Digest"}[kind]
        pct=lambda key:"N/A" if not changes.get(key) or changes[key].get("Change %") is None else f"{changes[key]['Change %']:+.1f}%"
        lines=[f"🗂️ **{label} — {start} to {end}**","",f"Compared with {previous_start} to {previous_end}.","",
               f"• Net sales: {float(metrics.get('net_sales') or 0):,.0f} Ks ({pct('net_sales')})",f"• Transactions: {int(metrics.get('transactions') or 0)} ({pct('transactions')})",
               f"• Gross profit: {float(metrics.get('gross_profit') or 0):,.0f} Ks ({pct('gross_profit')})",f"• Expenses: {float(metrics.get('expenses') or 0):,.0f} Ks ({pct('expenses')})",
               f"• Net profit: {float(metrics.get('net_profit') or 0):,.0f} Ks ({pct('net_profit')})",f"• Alerts: {len(alerts)}"]
        if alerts:lines.extend(["","Top alerts:"]+[f"• {row['Severity']} — {row['Title']}: {row['Evidence']}" for row in alerts[:5]])
        lines.extend(["","Generated and stored locally. No email, Telegram, or external notification was sent."]);return "\n".join(lines)

    @staticmethod
    def _rows(metrics,changes,alerts):
        rows=[{"Section":"Metric","Name":key,"Value":value,"Change %":(changes.get(key) or {}).get("Change %")} for key,value in metrics.items() if value is not None]
        rows.extend({"Section":"Alert","Name":row.get("Title"),"Value":row.get("Severity"),"Change %":None} for row in alerts);return rows

    @staticmethod
    def _result(message,data,kind,start,end,payload=None):
        return {"type":"dashboard_digest","message":message,"data":data,"sql":"","digest_kind":kind,"start_date":start,"end_date":end,"payload":payload or {},"_required_permissions":["dashboard"]}


class DashboardDigestScheduler:
    """Generate completed-period digests once while the desktop app is running."""
    @classmethod
    def run_due(cls,user_id,role,today=None):
        if str(role or "").lower() not in ("admin","manager"):return []
        if not cls.enabled():return []
        permissions=DashboardDigestService._permissions(user_id)
        if "dashboard" not in permissions:return []
        today=today or date.today();specs=[]
        yesterday=today-timedelta(days=1);specs.append(("daily",yesterday,yesterday))
        this_week=today-timedelta(days=today.weekday());week_end=this_week-timedelta(days=1);specs.append(("weekly",week_end-timedelta(days=6),week_end))
        month_end=today.replace(day=1)-timedelta(days=1);specs.append(("monthly",month_end.replace(day=1),month_end))
        return [DashboardDigestService.generate(kind,start.isoformat(),end.isoformat(),user_id,permissions) for kind,start,end in specs]

    @staticmethod
    def enabled():
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("SELECT value FROM settings WHERE key='ai_dashboard_digest_enabled'");row=cursor.fetchone()
            return str(row[0] if row else "1").strip().lower() in ("1","true","yes","on")
        finally:conn.close()
