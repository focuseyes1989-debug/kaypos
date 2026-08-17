"""Governance, provenance and privacy-safe audit records for Dashboard AI."""

from datetime import datetime

from models.database import connect_db
from utils.db_compat import integer_primary_key_sql
from utils.permissions import PermissionManager


class DashboardAIGovernance:
    RESULT_TYPES = {"dashboard_summary", "dashboard_comparison", "dashboard_chart", "dashboard_alerts", "dashboard_explanation", "dashboard_digest"}

    @classmethod
    def ensure_schema(cls):
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute(f"""CREATE TABLE IF NOT EXISTS ai_dashboard_audit(
                id {integer_primary_key_sql()},user_id INTEGER,query_text TEXT NOT NULL,
                result_type TEXT NOT NULL,data_scope TEXT NOT NULL,period_start TEXT,period_end TEXT,
                sources TEXT,success INTEGER NOT NULL DEFAULT 1,response_ms INTEGER NOT NULL DEFAULT 0,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            conn.commit()
        finally:conn.close()

    @staticmethod
    def sources_for(result):
        sources=["sales","sale_items","products"]
        metrics=result.get("metrics") or (result.get("payload") or {}).get("metrics") or {}
        if metrics.get("expenses") is not None:sources.append("expenses")
        if metrics.get("outstanding_credit") is not None:sources.extend(["customers","credit"])
        if metrics.get("open_cash_sessions") is not None:sources.append("cash_sessions")
        if metrics.get("attendance_issues") is not None:sources.append("attendance")
        if result.get("type")=="dashboard_digest":sources.append("ai_dashboard_digests")
        return list(dict.fromkeys(sources))

    @classmethod
    def enrich(cls,result):
        if not isinstance(result,dict) or result.get("type") not in cls.RESULT_TYPES:return result
        generated=datetime.now().astimezone().isoformat(timespec="seconds");scope=result.get("scope") or "business";sources=cls.sources_for(result)
        result["provenance"]={"generated_at":generated,"scope":scope,"period_start":result.get("start_date"),"period_end":result.get("end_date"),"sources":sources,"method":"Deterministic read-only database calculation"}
        result["message"]=str(result.get("message") or "")+f"\n\n_Data scope: {scope} · Sources: {', '.join(sources)} · Generated: {generated}_"
        return result

    @classmethod
    def record(cls,query,user_id,result,response_seconds=0.0,success=True):
        if not isinstance(result,dict) or result.get("type") not in cls.RESULT_TYPES:return
        try:
            cls.ensure_schema();provenance=result.get("provenance") or {};conn=connect_db();cursor=conn.cursor()
            try:
                cursor.execute("""INSERT INTO ai_dashboard_audit(user_id,query_text,result_type,data_scope,period_start,period_end,sources,success,response_ms) VALUES(?,?,?,?,?,?,?,?,?)""",(
                    int(user_id) if str(user_id).isdigit() else None,str(query or "")[:500],str(result.get("type") or "unknown"),str(provenance.get("scope") or result.get("scope") or "business"),result.get("start_date"),result.get("end_date"),",".join(provenance.get("sources") or cls.sources_for(result)),1 if success else 0,max(0,int(float(response_seconds or 0)*1000))))
                conn.commit()
            finally:conn.close()
        except Exception:return

    @staticmethod
    def handles(query):
        text=(query or "").lower()
        return any(term in text for term in ("dashboard ai audit","dashboard audit","ai dashboard history","dashboard query history","dashboard စစ်ဆေးမှတ်တမ်း","dashboard မှတ်တမ်း"))

    @staticmethod
    def _role(user_id):
        try:user_id=int(user_id)
        except (TypeError,ValueError):return ""
        conn=connect_db();cursor=conn.cursor()
        try:
            cursor.execute("SELECT role FROM users WHERE id=?",(user_id,));row=cursor.fetchone()
            return str(row[0] or "").strip().lower() if row else ""
        except Exception:return ""
        finally:conn.close()

    @classmethod
    def handle(cls,query,user_id):
        if not cls.handles(query):return None
        permissions=PermissionManager.get_user_permissions(user_id) or set()
        if "dashboard" not in permissions or cls._role(user_id) not in ("admin","manager"):
            return {"type":"dashboard_audit","message":"🔒 Admin or Manager Dashboard permission is required to view AI audit history.","data":[],"sql":""}
        try:
            cls.ensure_schema();conn=connect_db();cursor=conn.cursor()
            try:
                cursor.execute("""SELECT generated_at,user_id,result_type,data_scope,period_start,period_end,response_ms,success FROM ai_dashboard_audit ORDER BY generated_at DESC,id DESC LIMIT 20""");rows=cursor.fetchall()
            finally:conn.close()
            data=[{"Generated":str(r[0]),"User ID":r[1],"Result":r[2],"Scope":r[3],"Period":f"{r[4] or '-'} to {r[5] or '-'}","Response ms":r[6],"Status":"OK" if r[7] else "Failed"} for r in rows]
            return {"type":"dashboard_audit","message":f"🛡️ **Dashboard AI Audit History**\n\nShowing {len(data)} most recent privacy-safe record(s). Query results and personal records are not duplicated in this log.","data":data,"sql":"","_required_permissions":["dashboard"]}
        except Exception as exc:return {"type":"dashboard_audit","message":f"❌ Dashboard AI audit history failed: {exc}","data":[],"sql":""}
