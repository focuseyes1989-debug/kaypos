"""Persistence and status queries for the LAN printer-agent registry."""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Callable

from models.database import connect_db
from utils.db_compat import ensure_column, integer_primary_key_sql


ONLINE_WINDOW_SECONDS = 30


class PrinterRegistry:
    def __init__(self, connection_factory: Callable = connect_db):
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS printer_agents (
                    agent_id TEXT PRIMARY KEY,
                    computer_name TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    platform TEXT,
                    agent_version TEXT,
                    last_seen TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_printers (
                    agent_id TEXT NOT NULL,
                    printer_name TEXT NOT NULL,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'online',
                    last_seen TEXT NOT NULL,
                    PRIMARY KEY (agent_id, printer_name),
                    FOREIGN KEY (agent_id) REFERENCES printer_agents(agent_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_printer_agents_seen ON printer_agents(last_seen)")
            ensure_column(cursor, "printer_agents", "api_key_hash", "TEXT")
            ensure_column(cursor, "printer_agents", "is_enabled", "INTEGER NOT NULL DEFAULT 1")
            ensure_column(cursor, "printer_agents", "allowed_job_types", "TEXT NOT NULL DEFAULT '[]'")
            ensure_column(cursor, "network_printers", "is_enabled", "INTEGER NOT NULL DEFAULT 1")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_printers_seen ON network_printers(last_seen)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_print_jobs (
                    job_id TEXT PRIMARY KEY,
                    request_key TEXT NOT NULL UNIQUE,
                    source_agent_id TEXT,
                    target_agent_id TEXT NOT NULL,
                    printer_name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    copies INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    claimed_at TEXT,
                    completed_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_print_jobs_queue ON network_print_jobs(target_agent_id, status, created_at)")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS network_print_audit (
                    id {integer_primary_key_sql()},
                    job_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail TEXT,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_print_audit_job ON network_print_audit(job_id, created_at)")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS printer_security_audit (
                    id {integer_primary_key_sql()},
                    event TEXT NOT NULL,
                    agent_id TEXT,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def heartbeat(
        self,
        agent_id: str,
        computer_name: str,
        ip_address: str,
        printers: list[dict],
        platform: str = "Windows",
        agent_version: str = "1.0",
    ) -> dict:
        agent_id = str(agent_id or "").strip()[:128]
        if not agent_id:
            raise ValueError("agent_id is required")
        computer_name = str(computer_name or "Unknown PC").strip()[:120]
        ip_address = str(ip_address or "unknown").strip()[:64]
        platform = str(platform or "").strip()[:80]
        agent_version = str(agent_version or "").strip()[:40]
        normalized = []
        seen_names = set()
        for item in printers or []:
            item = item if isinstance(item, dict) else {"name": item}
            name = str(item.get("name") or "").strip()[:255]
            if name and name not in seen_names:
                seen_names.add(name)
                normalized.append({"name": name, "is_default": bool(item.get("is_default"))})
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO printer_agents
                    (agent_id, computer_name, ip_address, platform, agent_version, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (agent_id) DO UPDATE SET
                    computer_name=excluded.computer_name,
                    ip_address=excluded.ip_address,
                    platform=excluded.platform,
                    agent_version=excluded.agent_version,
                    last_seen=excluded.last_seen
            """, (agent_id, computer_name, ip_address, platform, agent_version, stamp))
            cursor.execute(
                "UPDATE network_printers SET status='offline' WHERE agent_id=?",
                (agent_id,),
            )
            for item in normalized:
                cursor.execute("""
                    INSERT INTO network_printers
                        (agent_id, printer_name, is_default, status, last_seen)
                    VALUES (?, ?, ?, 'online', ?)
                    ON CONFLICT (agent_id, printer_name) DO UPDATE SET
                        is_default=excluded.is_default,
                        status='online',
                        last_seen=excluded.last_seen
                """, (
                    agent_id, item["name"], 1 if item["is_default"] else 0, stamp,
                ))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_agent(agent_id) or {}

    def enroll_agent(self, agent_id: str, computer_name: str) -> tuple[dict, str]:
        from server.printer_security import hash_secret

        agent_id = str(agent_id or "").strip()[:128]
        computer_name = str(computer_name or "Unknown PC").strip()[:120]
        if len(agent_id) < 8:
            raise ValueError("A valid agent_id is required")
        self.ensure_schema()
        token = secrets.token_urlsafe(32)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO printer_agents
                    (agent_id, computer_name, ip_address, platform, agent_version, last_seen,
                     api_key_hash, is_enabled, allowed_job_types)
                VALUES (?, ?, '', '', '', ?, ?, 1, '[]')
                ON CONFLICT (agent_id) DO UPDATE SET
                    computer_name=excluded.computer_name,
                    api_key_hash=excluded.api_key_hash,
                    is_enabled=1
            """, (agent_id, computer_name, stamp, hash_secret(token)))
            cursor.execute(
                "INSERT INTO printer_security_audit (event, agent_id, detail, created_at) VALUES (?, ?, ?, ?)",
                ("agent_enrolled", agent_id, f"computer={computer_name}; token_rotated=1", stamp),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_agent(agent_id) or {}, token

    def authorize_agent(self, agent_id: str, token: str, job_type: str = "") -> None:
        from server.printer_security import security_enabled, verify_secret

        if not security_enabled():
            return
        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT api_key_hash, is_enabled, allowed_job_types FROM printer_agents WHERE agent_id=?",
                (str(agent_id or ""),),
            )
            row = cursor.fetchone()
        finally:
            conn.close()
        if not row or not verify_secret(token, str(row[0] or "")):
            raise PermissionError("Invalid Printer Agent credentials")
        if not bool(row[1]):
            raise PermissionError("This Printer Agent has been disabled")
        allowed = json.loads(row[2] or "[]")
        if job_type and allowed and job_type not in allowed:
            raise PermissionError(f"Printer Agent is not allowed to process {job_type} jobs")

    def set_agent_permissions(self, agent_id: str, enabled: bool, allowed_job_types: list[str]) -> dict:
        supported = {"test_page", "pdf", "image", "text_receipt", "escpos_raw"}
        allowed = [item for item in dict.fromkeys(allowed_job_types or []) if item in supported]
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE printer_agents SET is_enabled=?, allowed_job_types=? WHERE agent_id=?",
                (1 if enabled else 0, json.dumps(allowed, separators=(",", ":")), agent_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Printer Agent not found")
            cursor.execute(
                "INSERT INTO printer_security_audit (event, agent_id, detail, created_at) VALUES (?, ?, ?, ?)",
                (
                    "permissions_updated",
                    agent_id,
                    f"enabled={1 if enabled else 0}; allowed={','.join(allowed) or 'all'}",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_agent(agent_id) or {}

    def set_printer_enabled(self, agent_id: str, printer_name: str, enabled: bool) -> dict:
        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE network_printers SET is_enabled=? WHERE agent_id=? AND printer_name=?",
                (1 if enabled else 0, str(agent_id or ""), str(printer_name or "")),
            )
            if cursor.rowcount != 1:
                raise ValueError("Printer not found")
            cursor.execute(
                "INSERT INTO printer_security_audit (event, agent_id, detail, created_at) VALUES (?, ?, ?, ?)",
                (
                    "printer_permission_updated", agent_id,
                    f"printer={printer_name}; enabled={1 if enabled else 0}",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return self.get_agent(agent_id) or {}

    def security_audit(self, limit: int = 100) -> list[dict]:
        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT event, agent_id, detail, created_at FROM printer_security_audit ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit or 100), 500)),),
            )
            return self._dict_rows(cursor)
        finally:
            conn.close()

    @staticmethod
    def _dict_rows(cursor) -> list[dict]:
        columns = [str(column[0]) for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def list_agents(self) -> list[dict]:
        self.ensure_schema()
        cutoff = (datetime.now() - timedelta(seconds=ONLINE_WINDOW_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT agent_id, computer_name, ip_address, platform, agent_version, last_seen,
                       is_enabled, allowed_job_types,
                       CASE WHEN last_seen >= ? THEN 1 ELSE 0 END AS is_online
                FROM printer_agents
                ORDER BY is_online DESC, computer_name, agent_id
            """, (cutoff,))
            agents = self._dict_rows(cursor)
            cursor.execute("""
                SELECT agent_id, printer_name, is_default, status, last_seen, is_enabled
                FROM network_printers
                ORDER BY is_default DESC, printer_name
            """)
            printers = self._dict_rows(cursor)
        finally:
            conn.close()

        by_agent: dict[str, list[dict]] = {}
        for printer in printers:
            printer["is_default"] = bool(printer.get("is_default"))
            printer["is_enabled"] = bool(printer.get("is_enabled"))
            by_agent.setdefault(str(printer["agent_id"]), []).append(printer)
        for agent in agents:
            agent["is_online"] = bool(agent.get("is_online"))
            agent["is_enabled"] = bool(agent.get("is_enabled"))
            try:
                agent["allowed_job_types"] = json.loads(agent.get("allowed_job_types") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                agent["allowed_job_types"] = []
            agent["printers"] = by_agent.get(str(agent["agent_id"]), [])
            if not agent["is_online"]:
                for printer in agent["printers"]:
                    printer["status"] = "offline"
        return agents

    def get_agent(self, agent_id: str) -> dict | None:
        return next((item for item in self.list_agents() if item["agent_id"] == agent_id), None)

    @staticmethod
    def _public_job(row: dict | None) -> dict | None:
        if not row:
            return None
        result = dict(row)
        try:
            result["payload"] = json.loads(result.pop("payload_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            result["payload"] = {}
            result.pop("payload_json", None)
        return result

    @staticmethod
    def _audit(cursor, job_id: str, event: str, detail: str, actor: str, stamp: str) -> None:
        cursor.execute("""
            INSERT INTO network_print_audit (job_id, event, detail, actor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, event, detail, actor, stamp))

    def _find_job(self, cursor, job_id: str) -> dict | None:
        cursor.execute("SELECT * FROM network_print_jobs WHERE job_id=?", (job_id,))
        rows = self._dict_rows(cursor)
        return rows[0] if rows else None

    def create_job(
        self,
        request_key: str,
        target_agent_id: str,
        printer_name: str,
        job_type: str = "test_page",
        payload: dict | None = None,
        copies: int = 1,
        source_agent_id: str = "server-manager",
        max_attempts: int = 3,
    ) -> dict:
        request_key = str(request_key or "").strip()[:128]
        if len(request_key) < 8:
            raise ValueError("request_key must contain at least 8 characters")
        target_agent_id = str(target_agent_id or "").strip()[:128]
        printer_name = str(printer_name or "").strip()[:255]
        job_type = str(job_type or "test_page").strip()[:40]
        if not target_agent_id or not printer_name:
            raise ValueError("target_agent_id and printer_name are required")
        if job_type not in {"test_page", "pdf", "image", "text_receipt", "escpos_raw"}:
            raise ValueError("Unsupported Phase 2 job type")
        copies = max(1, min(int(copies or 1), 99))
        max_attempts = max(1, min(int(max_attempts or 3), 10))
        payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
        if len(payload_json.encode("utf-8")) > 64 * 1024:
            raise ValueError("Print job payload is too large")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM network_print_jobs WHERE request_key=?", (request_key,))
            existing = self._dict_rows(cursor)
            if existing:
                return self._public_job(existing[0]) or {}
            cursor.execute(
                "SELECT is_enabled FROM network_printers WHERE agent_id=? AND printer_name=?",
                (target_agent_id, printer_name),
            )
            printer_row = cursor.fetchone()
            if printer_row is None:
                raise ValueError("The selected printer is not registered to that PC")
            if not bool(printer_row[0]):
                raise ValueError("The selected printer has been disabled")
            job_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO network_print_jobs
                    (job_id, request_key, source_agent_id, target_agent_id, printer_name,
                     job_type, payload_json, copies, status, attempts, max_attempts,
                     error_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, '', ?, ?)
            """, (
                job_id, request_key, str(source_agent_id or "")[:128], target_agent_id,
                printer_name, job_type, payload_json, copies, max_attempts, stamp, stamp,
            ))
            self._audit(cursor, job_id, "created", f"printer={printer_name}; type={job_type}", str(source_agent_id or "server"), stamp)
            conn.commit()
            return self._public_job(self._find_job(cursor, job_id)) or {}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def pending_jobs(self, agent_id: str, limit: int = 5) -> list[dict]:
        self.recover_stale_jobs()
        limit = max(1, min(int(limit or 5), 50))
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT jobs.* FROM network_print_jobs AS jobs
                JOIN network_printers AS printers
                  ON printers.agent_id=jobs.target_agent_id
                 AND printers.printer_name=jobs.printer_name
                WHERE jobs.target_agent_id=? AND jobs.status='pending'
                  AND jobs.attempts < jobs.max_attempts AND printers.is_enabled=1
                ORDER BY jobs.created_at, jobs.job_id LIMIT ?
            """, (str(agent_id or ""), limit))
            return [self._public_job(row) or {} for row in self._dict_rows(cursor)]
        finally:
            conn.close()

    def get_job(self, job_id: str) -> dict | None:
        self.ensure_schema()
        conn = self._connection_factory()
        try:
            return self._public_job(self._find_job(conn.cursor(), str(job_id or "")))
        finally:
            conn.close()

    def get_job_by_request_key(self, request_key: str) -> dict | None:
        self.ensure_schema()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM network_print_jobs WHERE request_key=?", (str(request_key or ""),))
            rows = self._dict_rows(cursor)
            return self._public_job(rows[0]) if rows else None
        finally:
            conn.close()

    def claim_job(self, job_id: str, agent_id: str, printer_names: list[str]) -> dict:
        names = {str(name or "").strip() for name in printer_names or []}
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            current = self._find_job(cursor, str(job_id or ""))
            if not current or current.get("target_agent_id") != agent_id:
                raise ValueError("Print job was not assigned to this agent")
            if current.get("printer_name") not in names:
                raise ValueError("Assigned printer is not installed on this agent")
            cursor.execute(
                "SELECT is_enabled FROM network_printers WHERE agent_id=? AND printer_name=?",
                (agent_id, current.get("printer_name")),
            )
            printer_row = cursor.fetchone()
            if not printer_row or not bool(printer_row[0]):
                raise ValueError("Assigned printer has been disabled")
            cursor.execute("""
                UPDATE network_print_jobs
                SET status='printing', attempts=attempts+1, claimed_at=?, updated_at=?, error_message=''
                WHERE job_id=? AND status='pending' AND attempts < max_attempts
            """, (stamp, stamp, job_id))
            if cursor.rowcount != 1:
                raise ValueError("Print job is no longer available")
            self._audit(cursor, job_id, "claimed", f"attempt={int(current.get('attempts') or 0) + 1}", agent_id, stamp)
            conn.commit()
            return self._public_job(self._find_job(cursor, job_id)) or {}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def finish_job(self, job_id: str, agent_id: str, status: str, error_message: str = "") -> dict:
        if status not in {"completed", "failed"}:
            raise ValueError("status must be completed or failed")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            current = self._find_job(cursor, str(job_id or ""))
            if not current or current.get("target_agent_id") != agent_id:
                raise ValueError("Print job was not assigned to this agent")
            if current.get("status") != "printing":
                raise ValueError("Only a printing job can be completed or failed")
            completed_at = stamp if status == "completed" else None
            cursor.execute("""
                UPDATE network_print_jobs SET status=?, error_message=?, updated_at=?, completed_at=?
                WHERE job_id=? AND status='printing'
            """, (status, str(error_message or "")[:1000], stamp, completed_at, job_id))
            self._audit(cursor, job_id, status, str(error_message or "")[:1000], agent_id, stamp)
            conn.commit()
            return self._public_job(self._find_job(cursor, job_id)) or {}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def retry_job(self, job_id: str, actor: str = "server-manager") -> dict:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            current = self._find_job(cursor, str(job_id or ""))
            if not current or current.get("status") != "failed":
                raise ValueError("Only a failed print job can be retried")
            if int(current.get("attempts") or 0) >= int(current.get("max_attempts") or 0):
                raise ValueError("Print job has reached its retry limit")
            cursor.execute("""
                UPDATE network_print_jobs SET status='pending', error_message='', updated_at=?, claimed_at=NULL
                WHERE job_id=? AND status='failed'
            """, (stamp, job_id))
            self._audit(cursor, job_id, "retried", "Returned to pending queue", actor, stamp)
            conn.commit()
            return self._public_job(self._find_job(cursor, job_id)) or {}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def recover_stale_jobs(self, timeout_seconds: int = 60) -> int:
        cutoff = (datetime.now() - timedelta(seconds=max(10, timeout_seconds))).strftime("%Y-%m-%d %H:%M:%S")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM network_print_jobs WHERE status='printing' AND claimed_at<?", (cutoff,))
            job_ids = [str(row[0]) for row in cursor.fetchall()]
            for job_id in job_ids:
                cursor.execute("""
                    UPDATE network_print_jobs
                    SET status='failed', error_message='Print Agent timed out', updated_at=?
                    WHERE job_id=? AND status='printing'
                """, (stamp, job_id))
                self._audit(cursor, job_id, "timeout", "Print Agent timed out", "server", stamp)
            conn.commit()
            return len(job_ids)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_jobs(self, limit: int = 100) -> list[dict]:
        self.ensure_schema()
        self.recover_stale_jobs()
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM network_print_jobs ORDER BY created_at DESC, job_id DESC LIMIT ?", (max(1, min(int(limit or 100), 500)),))
            return [self._public_job(row) or {} for row in self._dict_rows(cursor)]
        finally:
            conn.close()

    def job_audit(self, job_id: str) -> list[dict]:
        conn = self._connection_factory()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT event, detail, actor, created_at FROM network_print_audit WHERE job_id=? ORDER BY id", (job_id,))
            return self._dict_rows(cursor)
        finally:
            conn.close()
