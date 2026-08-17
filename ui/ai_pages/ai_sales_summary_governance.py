"""Phase 10 governance, local digests and audit for Sales Summary AI."""

import hashlib,json
from datetime import date,timedelta,datetime

from models.database import connect_db
from ui.ai_pages.ai_sales_summary_queries import AISalesSummaryQueryHandler
from ui.ai_pages.ai_dashboard_queries import AIDashboardQueryHandler
from utils.db_compat import integer_primary_key_sql
from utils.permissions import PermissionManager


class SalesSummaryGovernance:
    RESULT_TYPES={"sales_summary_foundation","sales_summary_comparison","sales_summary_breakdown","sales_summary_chart","sales_summary_alerts","sales_summary_explanation","sales_summary_digest"}

    @classmethod
    def ensure_schema(cls):
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS ai_sales_summary_digests(id {integer_primary_key_sql()},digest_kind TEXT NOT NULL,period_start TEXT NOT NULL,period_end TEXT NOT NULL,data_scope TEXT NOT NULL,owner_key TEXT NOT NULL,created_by INTEGER,message TEXT NOT NULL,payload TEXT NOT NULL,generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(digest_kind,period_start,period_end,data_scope,owner_key))""")
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS ai_sales_summary_audit(id {integer_primary_key_sql()},user_id INTEGER,query_hash TEXT NOT NULL,result_type TEXT NOT NULL,data_scope TEXT NOT NULL,period_start TEXT,period_end TEXT,sources TEXT,response_ms INTEGER NOT NULL DEFAULT 0,success INTEGER NOT NULL DEFAULT 1,generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""");conn.commit()
        finally:conn.close()

    @staticmethod
    def permissions(user_id):
        try:return PermissionManager.get_user_permissions(int(user_id)) or set()
        except (TypeError,ValueError):return set()

    @staticmethod
    def context(user_id):return AIDashboardQueryHandler._user_context(user_id)

    @classmethod
    def enrich(cls,result):
        if not isinstance(result,dict) or result.get("type") not in cls.RESULT_TYPES:return result
        scope=result.get("scope") or "business";sources=["sales","sale_items"]
        if result.get("analysis_kind") in ("categories","cashiers") or result.get("type") in ("sales_summary_alerts","sales_summary_explanation"):sources.extend(["products","users","employees"])
        generated=datetime.now().astimezone().isoformat(timespec="seconds");sources=list(dict.fromkeys(sources))
        result["provenance"]={"scope":scope,"generated_at":generated,"period_start":result.get("start_date"),"period_end":result.get("end_date"),"sources":sources,"method":"Deterministic read-only database calculation"}
        result["message"]=str(result.get("message") or "")+f"\n\n_Data scope: {scope} · Sources: {', '.join(sources)} · Generated: {generated}_";return result

    @classmethod
    def record(cls,query,user_id,result,response_seconds=0,success=True):
        if not isinstance(result,dict) or result.get("type") not in cls.RESULT_TYPES:return
        try:
            cls.ensure_schema();provenance=result.get("provenance") or {};conn=connect_db();cursor=conn.cursor()
            try:
                cursor.execute("INSERT INTO ai_sales_summary_audit(user_id,query_hash,result_type,data_scope,period_start,period_end,sources,response_ms,success) VALUES(?,?,?,?,?,?,?,?,?)",(int(user_id) if str(user_id).isdigit() else None,hashlib.sha256(str(query or "").encode("utf-8")).hexdigest(),result.get("type"),provenance.get("scope") or result.get("scope") or "business",result.get("start_date"),result.get("end_date"),",".join(provenance.get("sources") or []),max(0,int(float(response_seconds or 0)*1000)),1 if success else 0));conn.commit()
            finally:conn.close()
        except Exception:return

    @staticmethod
    def handles_audit(query):
        text=(query or "").lower();return any(term in text for term in ("sales ai audit","sales summary audit","sales query history","အရောင်း ai စစ်ဆေးမှတ်တမ်း","အရောင်းမှတ်တမ်း စစ်"))

    @classmethod
    def audit_history(cls,query,user_id):
        if not cls.handles_audit(query):return None
        context=cls.context(user_id);permissions=cls.permissions(user_id)
        if str(context.get("role") or "").lower() not in ("admin","manager") or "sales_summary" not in permissions:return {"type":"sales_summary_audit","message":"🔒 Admin or Manager Sales Summary permission is required.","data":[],"sql":""}
        cls.ensure_schema();conn=connect_db();cursor=conn.cursor()
        try:cursor.execute("SELECT generated_at,user_id,result_type,data_scope,period_start,period_end,response_ms,success FROM ai_sales_summary_audit ORDER BY generated_at DESC,id DESC LIMIT 20");rows=cursor.fetchall()
        finally:conn.close()
        data=[{"Generated":str(r[0]),"User ID":r[1],"Result":r[2],"Scope":r[3],"Period":f"{r[4] or '-'} to {r[5] or '-'}","Response ms":r[6],"Status":"OK" if r[7] else "Failed"} for r in rows]
        return {"type":"sales_summary_audit","message":f"🛡️ **Sales Summary AI Audit**\n\nShowing {len(data)} privacy-safe metadata record(s). Raw queries and result rows are not stored.","data":data,"sql":"","_required_permissions":["sales_summary"]}


class SalesSummaryDigestService:
    @staticmethod
    def handles(query):
        text=(query or "").lower();return any(term in text for term in ("daily sales closing","sales closing summary","weekly sales review","monthly sales report","sales management report","latest sales digest","နေ့စဉ် အရောင်းပိတ်စာရင်း","အပတ်စဉ် အရောင်းသုံးသပ်ချက်","လစဉ် အရောင်းအစီရင်ခံစာ"))

    @classmethod
    def handle(cls,query,user_id):
        if not cls.handles(query):return None
        permissions=SalesSummaryGovernance.permissions(user_id);context=SalesSummaryGovernance.context(user_id);role=str(context.get("role") or "").lower();company=role in ("admin","manager") and bool({"sales_summary","reports"}&set(permissions));personal=not company and "sales" in permissions
        if not company and not personal:return cls.result("🔒 Sales Summary or personal Sales permission is required.",[],"daily",None,None)
        text=(query or "").lower();kind="monthly" if "monthly" in text or "လစဉ်" in text else "weekly" if "weekly" in text or "အပတ်စဉ်" in text else "daily"
        if "latest" in text or "နောက်ဆုံး" in text:return cls.latest(user_id,"business" if company else "personal",context)
        start,end=cls.current_period(kind);return cls.generate(kind,start,end,user_id,"business" if company else "personal",context)

    @staticmethod
    def current_period(kind,today=None):
        today=today or date.today()
        if kind=="weekly":return (today-timedelta(days=today.weekday())).isoformat(),today.isoformat()
        if kind=="monthly":return today.replace(day=1).isoformat(),today.isoformat()
        return today.isoformat(),today.isoformat()

    @classmethod
    def metrics(cls,start,end,scope,context):
        if scope=="business":return AISalesSummaryQueryHandler.collect(start,end)
        rows=AISalesSummaryQueryHandler.collect_cashiers(start,end,context.get("username"));row=rows[0] if rows else {}
        return {"gross_sales":float(row.get("Sales") or 0)+float(row.get("Discounts") or 0),"net_sales":float(row.get("Sales") or 0),"transactions":int(row.get("Transactions") or 0),"items_sold":float(row.get("Items Sold") or 0),"average_sale":float(row.get("Average Sale") or 0),"discounts":float(row.get("Discounts") or 0),"refunds":float(row.get("Refunds") or 0)}

    @classmethod
    def generate(cls,kind,start,end,user_id,scope="business",context=None):
        context=context or SalesSummaryGovernance.context(user_id);owner=str(context.get("username") or user_id) if scope=="personal" else "company";SalesSummaryGovernance.ensure_schema()
        existing=cls._load(kind,start,end,scope,owner)
        if existing:return existing
        current=cls.metrics(start,end,scope,context);previous_start,previous_end=cls.previous_period(start,end);previous=cls.metrics(previous_start,previous_end,scope,context);changes=AISalesSummaryQueryHandler.compare_metrics(current,previous)
        message=cls.message(kind,start,end,previous_start,previous_end,current,changes,scope,context);payload={"metrics":current,"previous_metrics":previous,"changes":changes,"previous_start":previous_start,"previous_end":previous_end,"scope_label":context.get("full_name") or context.get("username")}
        conn=connect_db();cursor=conn.cursor()
        try:cursor.execute("INSERT INTO ai_sales_summary_digests(digest_kind,period_start,period_end,data_scope,owner_key,created_by,message,payload) VALUES(?,?,?,?,?,?,?,?)",(kind,start,end,scope,owner,int(user_id) if str(user_id).isdigit() else None,message,json.dumps(payload,ensure_ascii=False)));conn.commit()
        except Exception:
            conn.rollback();return cls._load(kind,start,end,scope,owner) or cls.result("❌ Sales digest could not be stored.",[],kind,start,end)
        finally:conn.close()
        return cls.result(message,cls.rows(current,changes),kind,start,end,payload,scope)

    @classmethod
    def latest(cls,user_id,scope,context):
        SalesSummaryGovernance.ensure_schema();owner=str(context.get("username") or user_id) if scope=="personal" else "company";conn=connect_db();cursor=conn.cursor()
        try:cursor.execute("SELECT digest_kind,period_start,period_end,message,payload FROM ai_sales_summary_digests WHERE data_scope=? AND owner_key=? ORDER BY generated_at DESC,id DESC LIMIT 1",(scope,owner));row=cursor.fetchone()
        finally:conn.close()
        if not row:return cls.result("📭 No Sales Summary digest has been generated yet.",[],"daily",None,None,scope=scope)
        payload=json.loads(row[4] or "{}");return cls.result(row[3],cls.rows(payload.get("metrics",{}),payload.get("changes",{})),row[0],row[1],row[2],payload,scope)

    @classmethod
    def _load(cls,kind,start,end,scope,owner):
        conn=connect_db();cursor=conn.cursor()
        try:cursor.execute("SELECT message,payload FROM ai_sales_summary_digests WHERE digest_kind=? AND period_start=? AND period_end=? AND data_scope=? AND owner_key=?",(kind,start,end,scope,owner));row=cursor.fetchone()
        finally:conn.close()
        if not row:return None
        payload=json.loads(row[1] or "{}");return cls.result(row[0],cls.rows(payload.get("metrics",{}),payload.get("changes",{})),kind,start,end,payload,scope)

    @staticmethod
    def previous_period(start,end):
        first,last=date.fromisoformat(start),date.fromisoformat(end);days=(last-first).days+1;previous_end=first-timedelta(days=1);return (previous_end-timedelta(days=days-1)).isoformat(),previous_end.isoformat()

    @staticmethod
    def message(kind,start,end,previous_start,previous_end,metrics,changes,scope,context):
        label={"daily":"Daily Sales Closing","weekly":"Weekly Sales Review","monthly":"Monthly Sales Report"}[kind];pct=lambda key:"N/A" if (changes.get(key) or {}).get("Change %") is None else f"{changes[key]['Change %']:+.1f}%"
        owner=f" — {context.get('full_name') or context.get('username')}" if scope=="personal" else ""
        return "\n".join([f"🧾 **{label}{owner} — {start} to {end}**",f"Compared with {previous_start} to {previous_end}.","",f"• Net Sales: {float(metrics.get('net_sales') or 0):,.0f} Ks ({pct('net_sales')})",f"• Transactions: {int(metrics.get('transactions') or 0)} ({pct('transactions')})",f"• Items Sold: {float(metrics.get('items_sold') or 0):,.2f} ({pct('items_sold')})",f"• Average Sale: {float(metrics.get('average_sale') or 0):,.0f} Ks ({pct('average_sale')})",f"• Discounts: {float(metrics.get('discounts') or 0):,.0f} Ks",f"• Refunds: {float(metrics.get('refunds') or 0):,.0f} Ks","","Generated and stored locally. No external notification was sent."])

    @staticmethod
    def rows(metrics,changes):return [{"Metric":key,"Value":value,"Change %":(changes.get(key) or {}).get("Change %")} for key,value in metrics.items()]

    @staticmethod
    def result(message,data,kind,start,end,payload=None,scope="business"):return {"type":"sales_summary_digest","message":message,"data":data,"sql":"","digest_kind":kind,"start_date":start,"end_date":end,"payload":payload or {},"scope":scope,"_required_permissions":["sales_summary"] if scope=="business" else ["sales"]}


class SalesSummaryDigestScheduler:
    @classmethod
    def run_due(cls,user_id,role,today=None):
        if str(role or "").lower() not in ("admin","manager") or not cls.enabled():return []
        permissions=SalesSummaryGovernance.permissions(user_id)
        if not ({"sales_summary","reports"}&set(permissions)):return []
        today=today or date.today();yesterday=today-timedelta(days=1);week_end=today-timedelta(days=today.weekday()+1);month_end=today.replace(day=1)-timedelta(days=1);specs=[("daily",yesterday,yesterday),("weekly",week_end-timedelta(days=6),week_end),("monthly",month_end.replace(day=1),month_end)]
        return [SalesSummaryDigestService.generate(kind,start.isoformat(),end.isoformat(),user_id,"business",SalesSummaryGovernance.context(user_id)) for kind,start,end in specs]

    @staticmethod
    def enabled():
        conn=connect_db();cursor=conn.cursor()
        try:cursor.execute("SELECT value FROM settings WHERE key='ai_dashboard_digest_enabled'");row=cursor.fetchone();return str(row[0] if row else "1").lower() in ("1","true","yes","on")
        finally:conn.close()
