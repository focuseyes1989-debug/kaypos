"""Employee management data access for SQLite and PostgreSQL."""

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional

from models.database import connect_db
from utils.db_compat import ensure_column, is_postgres_backend


EMPLOYEE_TABLES = ("payrolls", "attendance", "employee_shifts", "shifts", "employees")


def _rows(cursor) -> list[Dict[str, Any]]:
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def ensure_employee_schema() -> None:
    conn = connect_db()
    cur = conn.cursor()
    pk = "SERIAL PRIMARY KEY" if is_postgres_backend() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ensure_column(cur, "sales", "created_by", "TEXT")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS employees (
            id {pk}, employee_no TEXT UNIQUE NOT NULL, user_id INTEGER UNIQUE,
            full_name TEXT NOT NULL, phone TEXT, address TEXT, date_of_birth TEXT,
            national_id TEXT, photo_path TEXT, hire_date TEXT NOT NULL,
            position TEXT, department TEXT, branch TEXT, employment_status TEXT DEFAULT 'Active',
            emergency_contact_name TEXT, emergency_contact_phone TEXT, notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    ensure_column(cur, "employees", "zkteco_user_id", "TEXT")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS shifts (
            id {pk}, name TEXT UNIQUE NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            break_minutes INTEGER DEFAULT 0, is_overnight INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS employee_shifts (
            id {pk}, employee_id INTEGER NOT NULL, shift_id INTEGER NOT NULL,
            effective_from TEXT NOT NULL, effective_to TEXT, weekly_off_days TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE CASCADE
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS attendance (
            id {pk}, employee_id INTEGER NOT NULL, attendance_date TEXT NOT NULL,
            check_in TEXT, check_out TEXT, status TEXT DEFAULT 'Present', late_minutes INTEGER DEFAULT 0,
            notes TEXT, corrected_by INTEGER, correction_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, attendance_date),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
            FOREIGN KEY (corrected_by) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS payrolls (
            id {pk}, payroll_no TEXT UNIQUE NOT NULL, employee_id INTEGER NOT NULL,
            period_month TEXT NOT NULL, basic_salary DOUBLE PRECISION DEFAULT 0,
            allowance DOUBLE PRECISION DEFAULT 0, overtime_amount DOUBLE PRECISION DEFAULT 0,
            bonus DOUBLE PRECISION DEFAULT 0, late_deduction DOUBLE PRECISION DEFAULT 0,
            absence_deduction DOUBLE PRECISION DEFAULT 0, advance_deduction DOUBLE PRECISION DEFAULT 0,
            other_deduction DOUBLE PRECISION DEFAULT 0, net_salary DOUBLE PRECISION DEFAULT 0,
            status TEXT DEFAULT 'Draft', paid_date TEXT, payment_method TEXT, expense_id INTEGER,
            notes TEXT, created_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employee_id, period_month),
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE RESTRICT,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE SET NULL
        )
    """)
    cur.execute(f"""CREATE TABLE IF NOT EXISTS employee_leave (
        id {pk}, employee_id INTEGER NOT NULL, leave_type TEXT NOT NULL,
        start_date TEXT NOT NULL, end_date TEXT NOT NULL, days DOUBLE PRECISION DEFAULT 1,
        reason TEXT, status TEXT DEFAULT 'Pending', reviewed_by INTEGER, reviewed_at TIMESTAMP,
        review_notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE,
        FOREIGN KEY(reviewed_by) REFERENCES users(id) ON DELETE SET NULL)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS employee_documents (
        id {pk}, employee_id INTEGER NOT NULL, document_type TEXT NOT NULL,
        document_no TEXT, file_path TEXT, issued_date TEXT, expiry_date TEXT,
        notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS salary_advances (
        id {pk}, employee_id INTEGER NOT NULL, advance_date TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL, repaid_amount DOUBLE PRECISION DEFAULT 0,
        status TEXT DEFAULT 'Outstanding', notes TEXT, created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE RESTRICT)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS commission_rules (
        id {pk}, employee_id INTEGER UNIQUE NOT NULL, rate_percent DOUBLE PRECISION DEFAULT 0,
        target_amount DOUBLE PRECISION DEFAULT 0, active INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS cash_sessions (
        id {pk}, employee_id INTEGER NOT NULL, opened_at TIMESTAMP NOT NULL,
        opening_cash DOUBLE PRECISION DEFAULT 0, closed_at TIMESTAMP,
        expected_cash DOUBLE PRECISION, actual_cash DOUBLE PRECISION, difference DOUBLE PRECISION,
        status TEXT DEFAULT 'Open', notes TEXT, opened_by INTEGER, closed_by INTEGER,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE RESTRICT)""")
    for sql in (
        "CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(employment_status)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date)",
        "CREATE INDEX IF NOT EXISTS idx_payroll_period ON payrolls(period_month, status)",
        "CREATE INDEX IF NOT EXISTS idx_employee_shifts_employee ON employee_shifts(employee_id, effective_from)",
        "CREATE INDEX IF NOT EXISTS idx_employee_leave_dates ON employee_leave(start_date, end_date, status)",
        "CREATE INDEX IF NOT EXISTS idx_employee_documents_expiry ON employee_documents(expiry_date)",
        "CREATE INDEX IF NOT EXISTS idx_salary_advances_employee ON salary_advances(employee_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_cash_sessions_status ON cash_sessions(status, opened_at)",
    ):
        cur.execute(sql)
    for name, start, end in (("Morning", "08:00", "20:00"), ("Evening", "14:00", "22:00")):
        if is_postgres_backend():
            cur.execute("INSERT INTO shifts(name,start_time,end_time) VALUES(?,?,?) ON CONFLICT(name) DO NOTHING", (name, start, end))
        else:
            cur.execute("INSERT OR IGNORE INTO shifts(name,start_time,end_time) VALUES(?,?,?)", (name, start, end))
    # One-time upgrade of the original Morning default. Custom schedules are
    # preserved because only the exact legacy 08:00-17:00 value is changed.
    cur.execute("UPDATE shifts SET end_time='20:00' WHERE name='Morning' AND start_time='08:00' AND end_time='17:00'")
    # Existing installations receive employee permissions without replacing custom roles.
    cur.execute("SELECT name, permissions FROM user_roles WHERE name IN ('Admin','Manager')")
    for role, permissions in cur.fetchall():
        values = {p for p in (permissions or "").split(",") if p}
        values.update({"employees", "manage_employees", "attendance", "manage_attendance", "shifts", "manage_shifts", "leave", "manage_leave", "employee_documents", "employee_performance"})
        if role == "Admin":
            values.update({"payroll", "manage_payroll", "employee_finance", "manage_employee_finance", "cash_sessions", "manage_cash_sessions"})
        cur.execute("UPDATE user_roles SET permissions=? WHERE name=?", (",".join(sorted(values)), role))
    conn.commit()
    conn.close()


def next_number(prefix: str, table: str) -> str:
    if table not in {"employees", "payrolls"}:
        raise ValueError("Unsupported number sequence")
    conn = connect_db(); cur = conn.cursor()
    column = "employee_no" if table == "employees" else "payroll_no"
    cur.execute(f"SELECT {column} FROM {table} WHERE {column} LIKE ? ORDER BY id DESC LIMIT 1", (f"{prefix}-%",))
    row = cur.fetchone(); conn.close()
    try: number = int(row[0].rsplit("-", 1)[1]) + 1 if row else 1
    except (ValueError, IndexError): number = 1
    return f"{prefix}-{number:04d}"


def list_employees(search: str = "", status: str = "All") -> list[Dict[str, Any]]:
    conn = connect_db(); cur = conn.cursor()
    sql = """SELECT e.*, u.username FROM employees e LEFT JOIN users u ON u.id=e.user_id WHERE 1=1"""
    params: list[Any] = []
    if search:
        sql += " AND (LOWER(e.full_name) LIKE ? OR LOWER(e.employee_no) LIKE ? OR e.phone LIKE ?)"
        term = f"%{search.lower()}%"; params += [term, term, term]
    if status != "All": sql += " AND e.employment_status=?"; params.append(status)
    cur.execute(sql + " ORDER BY e.id DESC", params); result = _rows(cur); conn.close(); return result


def save_employee(data: Dict[str, Any], employee_id: Optional[int] = None) -> int:
    conn = connect_db(); cur = conn.cursor()
    fields = ["employee_no","user_id","full_name","phone","address","date_of_birth","national_id","photo_path","hire_date","position","department","branch","employment_status","emergency_contact_name","emergency_contact_phone","notes","zkteco_user_id"]
    values = [data.get(f) or None for f in fields]
    try:
        if employee_id is not None:
            cur.execute(f"UPDATE employees SET {','.join(f'{f}=?' for f in fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", values + [employee_id])
            result = employee_id
        else:
            cur.execute(f"INSERT INTO employees({','.join(fields)}) VALUES({','.join('?' for _ in fields)})", values)
            result = cur.lastrowid
            # Some PostgreSQL/pooled cursor adapters do not expose lastrowid.
            if result is None:
                cur.execute("SELECT id FROM employees WHERE employee_no=?", (data.get("employee_no"),))
                row = cur.fetchone()
                result = row[0] if row else None
        if result is None:
            raise RuntimeError("Employee was saved but its database ID could not be retrieved")
        conn.commit()
        return int(result)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_users() -> list[tuple]:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT id, username, full_name FROM users WHERE is_active=1 ORDER BY username"); rows=cur.fetchall(); conn.close(); return rows


def list_shifts() -> list[Dict[str, Any]]:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT * FROM shifts WHERE is_active=1 ORDER BY name"); rows=_rows(cur); conn.close(); return rows


def save_shift(name: str, start: str, end: str, break_minutes: int, overnight: bool) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("INSERT INTO shifts(name,start_time,end_time,break_minutes,is_overnight) VALUES(?,?,?,?,?)", (name,start,end,break_minutes,int(overnight))); conn.commit(); conn.close()


def assign_shift(employee_id: int, shift_id: int, effective_from: str, weekly_off_days: str = "") -> int:
    conn=connect_db(); cur=conn.cursor()
    try:
        cur.execute("SELECT id FROM employee_shifts WHERE employee_id=? AND effective_from=?",(employee_id,effective_from));row=cur.fetchone()
        if row:
            cur.execute("UPDATE employee_shifts SET shift_id=?,weekly_off_days=?,effective_to=NULL WHERE id=?",(shift_id,weekly_off_days or None,row[0]));result=row[0]
        else:
            cur.execute("INSERT INTO employee_shifts(employee_id,shift_id,effective_from,weekly_off_days) VALUES(?,?,?,?)",(employee_id,shift_id,effective_from,weekly_off_days or None));result=cur.lastrowid
            if result is None:
                cur.execute("SELECT id FROM employee_shifts WHERE employee_id=? AND effective_from=?",(employee_id,effective_from));result=cur.fetchone()[0]
        conn.commit();return int(result)
    except Exception:conn.rollback();raise
    finally:conn.close()


def list_employee_shift_assignments() -> list[Dict[str,Any]]:
    conn=connect_db();cur=conn.cursor();cur.execute("""SELECT es.id,es.employee_id,e.employee_no,e.full_name,es.shift_id,s.name shift_name,s.start_time,s.end_time,es.effective_from,es.effective_to,es.weekly_off_days FROM employee_shifts es JOIN employees e ON e.id=es.employee_id JOIN shifts s ON s.id=es.shift_id ORDER BY es.effective_from DESC,e.full_name""");rows=_rows(cur);conn.close();return rows


def recalculate_attendance_categories(employee_id: Optional[int] = None) -> Dict[str,int]:
    """Classify imported attendance while preserving manually corrected rows."""
    conn=connect_db();cur=conn.cursor();sql="""SELECT a.id,a.employee_id,a.attendance_date,a.check_in,a.check_out,a.correction_reason FROM attendance a WHERE (a.correction_reason IS NULL OR a.correction_reason='')""";params=[]
    if employee_id is not None:sql+=" AND a.employee_id=?";params=[employee_id]
    cur.execute(sql,params);rows=cur.fetchall();counts={"Present":0,"Late":0,"Incomplete":0,"Leave":0,"Absent":0}
    for attendance_id,emp_id,day,check_in,check_out,_reason in rows:
        cur.execute("SELECT 1 FROM employee_leave WHERE employee_id=? AND status='Approved' AND ? BETWEEN start_date AND end_date LIMIT 1",(emp_id,day));on_leave=bool(cur.fetchone())
        cur.execute("""SELECT s.start_time FROM employee_shifts es JOIN shifts s ON s.id=es.shift_id WHERE es.employee_id=? AND es.effective_from<=? AND (es.effective_to IS NULL OR es.effective_to>=?) ORDER BY es.effective_from DESC LIMIT 1""",(emp_id,day,day));shift=cur.fetchone()
        late=0
        if on_leave:status="Leave"
        elif not check_in and not check_out:status="Absent"
        elif not check_in or not check_out or str(check_out)==str(check_in):status="Incomplete"
        elif shift and str(check_in)>str(shift[0]):
            start_h,start_m=map(int,str(shift[0])[:5].split(':'));in_h,in_m=map(int,str(check_in)[:5].split(':'));late=max(0,(in_h*60+in_m)-(start_h*60+start_m));status="Late" if late else "Present"
        else:status="Present"
        cur.execute("UPDATE attendance SET status=?,late_minutes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,late,attendance_id));counts[status]+=1
    conn.commit();conn.close();return counts


def list_attendance(day: str, to_day: Optional[str] = None) -> list[Dict[str, Any]]:
    conn=connect_db(); cur=conn.cursor()
    if to_day and to_day != day:
        cur.execute("""SELECT a.*,e.employee_no,e.full_name FROM attendance a JOIN employees e ON e.id=a.employee_id WHERE a.attendance_date BETWEEN ? AND ? ORDER BY a.attendance_date DESC,e.full_name""",(day,to_day))
    else:
        cur.execute("""SELECT a.*,e.employee_no,e.full_name FROM attendance a JOIN employees e ON e.id=a.employee_id WHERE a.attendance_date=? ORDER BY e.full_name""",(day,))
    rows=_rows(cur); conn.close(); return rows


def save_attendance(employee_id: int, day: str, check_in: str, check_out: str, status: str, notes: str, user_id: int, reason: str) -> None:
    conn=connect_db(); cur=conn.cursor()
    params=(check_in or None,check_out or None,status,notes or None,user_id,reason or None,employee_id,day)
    cur.execute("SELECT id FROM attendance WHERE employee_id=? AND attendance_date=?",(employee_id,day)); row=cur.fetchone()
    if row: cur.execute("UPDATE attendance SET check_in=?,check_out=?,status=?,notes=?,corrected_by=?,correction_reason=?,updated_at=CURRENT_TIMESTAMP WHERE employee_id=? AND attendance_date=?",params)
    else: cur.execute("INSERT INTO attendance(check_in,check_out,status,notes,corrected_by,correction_reason,employee_id,attendance_date) VALUES(?,?,?,?,?,?,?,?)",params)
    conn.commit(); conn.close()


def list_payrolls(period: str = "") -> list[Dict[str, Any]]:
    conn=connect_db(); cur=conn.cursor(); sql="""SELECT p.*,e.employee_no,e.full_name FROM payrolls p JOIN employees e ON e.id=p.employee_id"""; params=[]
    if period: sql += " WHERE p.period_month=?"; params=[period]
    cur.execute(sql+" ORDER BY p.period_month DESC,e.full_name",params); rows=_rows(cur); conn.close(); return rows


def save_payroll(data: Dict[str, Any], user_id: int) -> None:
    income=sum(float(data.get(k,0) or 0) for k in ("basic_salary","allowance","overtime_amount","bonus"))
    deductions=sum(float(data.get(k,0) or 0) for k in ("late_deduction","absence_deduction","advance_deduction","other_deduction"))
    conn=connect_db(); cur=conn.cursor(); cur.execute("""INSERT INTO payrolls(payroll_no,employee_id,period_month,basic_salary,allowance,overtime_amount,bonus,late_deduction,absence_deduction,advance_deduction,other_deduction,net_salary,notes,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(next_number("PAY","payrolls"),data["employee_id"],data["period_month"],data.get("basic_salary",0),data.get("allowance",0),data.get("overtime_amount",0),data.get("bonus",0),data.get("late_deduction",0),data.get("absence_deduction",0),data.get("advance_deduction",0),data.get("other_deduction",0),income-deductions,data.get("notes"),user_id)); conn.commit(); conn.close()


def pay_payroll(payroll_id: int, paid_date: str, method: str, username: str) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT payroll_no,net_salary,period_month,employee_id,status FROM payrolls WHERE id=?",(payroll_id,)); row=cur.fetchone()
    if not row or row[4] == "Paid": conn.close(); return
    payroll_no, amount, period, employee_id, _ = row
    cur.execute("SELECT full_name FROM employees WHERE id=?",(employee_id,)); employee=cur.fetchone()[0]
    expense_no=f"SAL-{payroll_no}"
    cur.execute("""INSERT INTO expenses(expense_no,category,description,amount,expense_date,payment_method,created_by,notes) VALUES(?,?,?,?,?,?,?,?)""",(expense_no,"Salaries",f"Salary - {employee} ({period})",amount,paid_date,method,username,payroll_no))
    expense_id=cur.lastrowid
    cur.execute("UPDATE payrolls SET status='Paid',paid_date=?,payment_method=?,expense_id=? WHERE id=?",(paid_date,method,expense_id,payroll_id)); conn.commit(); conn.close()


def list_leave(status: str = "All") -> list[Dict[str, Any]]:
    conn=connect_db(); cur=conn.cursor(); sql="""SELECT l.*,e.employee_no,e.full_name FROM employee_leave l JOIN employees e ON e.id=l.employee_id"""; params=[]
    if status != "All": sql += " WHERE l.status=?"; params=[status]
    cur.execute(sql+" ORDER BY l.start_date DESC",params); rows=_rows(cur); conn.close(); return rows


def create_leave(employee_id: int, leave_type: str, start: str, end: str, days: float, reason: str) -> None:
    if end < start: raise ValueError("End date cannot be before start date")
    conn=connect_db(); cur=conn.cursor(); cur.execute("INSERT INTO employee_leave(employee_id,leave_type,start_date,end_date,days,reason) VALUES(?,?,?,?,?,?)",(employee_id,leave_type,start,end,days,reason)); conn.commit(); conn.close()


def review_leave(leave_id: int, status: str, user_id: int, notes: str="") -> None:
    if status not in {"Approved","Rejected","Cancelled"}: raise ValueError("Invalid leave status")
    conn=connect_db(); cur=conn.cursor(); cur.execute("UPDATE employee_leave SET status=?,reviewed_by=?,reviewed_at=CURRENT_TIMESTAMP,review_notes=? WHERE id=?",(status,user_id,notes,leave_id)); conn.commit(); conn.close()


def list_documents(expiring_days: Optional[int]=None) -> list[Dict[str, Any]]:
    conn=connect_db(); cur=conn.cursor(); sql="""SELECT d.*,e.employee_no,e.full_name FROM employee_documents d JOIN employees e ON e.id=d.employee_id"""; params=[]
    if expiring_days is not None:
        if is_postgres_backend(): sql += " WHERE d.expiry_date IS NOT NULL AND CAST(d.expiry_date AS DATE) <= CURRENT_DATE + ? * INTERVAL '1 day'"
        else: sql += " WHERE d.expiry_date IS NOT NULL AND date(d.expiry_date) <= date('now', ?)"; params=[f"+{int(expiring_days)} days"]
        if is_postgres_backend(): params=[int(expiring_days)]
    cur.execute(sql+" ORDER BY d.expiry_date",params); rows=_rows(cur); conn.close(); return rows


def add_document(data: Dict[str,Any]) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("INSERT INTO employee_documents(employee_id,document_type,document_no,file_path,issued_date,expiry_date,notes) VALUES(?,?,?,?,?,?,?)",tuple(data.get(k) or None for k in ("employee_id","document_type","document_no","file_path","issued_date","expiry_date","notes"))); conn.commit(); conn.close()


def list_advances() -> list[Dict[str,Any]]:
    conn=connect_db(); cur=conn.cursor(); cur.execute("""SELECT a.*,e.employee_no,e.full_name,(a.amount-a.repaid_amount) balance FROM salary_advances a JOIN employees e ON e.id=a.employee_id ORDER BY a.advance_date DESC"""); rows=_rows(cur); conn.close(); return rows


def add_advance(employee_id:int, advance_date:str, amount:float, notes:str, user_id:int) -> None:
    if amount <= 0: raise ValueError("Advance amount must be greater than zero")
    conn=connect_db(); cur=conn.cursor(); cur.execute("INSERT INTO salary_advances(employee_id,advance_date,amount,notes,created_by) VALUES(?,?,?,?,?)",(employee_id,advance_date,amount,notes,user_id)); conn.commit(); conn.close()


def repay_advance(advance_id:int, amount:float) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT amount,repaid_amount FROM salary_advances WHERE id=?",(advance_id,)); row=cur.fetchone()
    if not row: conn.close(); raise ValueError("Advance not found")
    repaid=min(float(row[0]),float(row[1] or 0)+max(0,float(amount))); status="Repaid" if repaid>=float(row[0]) else "Outstanding"; cur.execute("UPDATE salary_advances SET repaid_amount=?,status=? WHERE id=?",(repaid,status,advance_id)); conn.commit(); conn.close()


def save_commission_rule(employee_id:int, rate:float, target:float) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT id FROM commission_rules WHERE employee_id=?",(employee_id,)); row=cur.fetchone()
    if row: cur.execute("UPDATE commission_rules SET rate_percent=?,target_amount=?,active=1,updated_at=CURRENT_TIMESTAMP WHERE employee_id=?",(rate,target,employee_id))
    else: cur.execute("INSERT INTO commission_rules(employee_id,rate_percent,target_amount) VALUES(?,?,?)",(employee_id,rate,target))
    conn.commit(); conn.close()


def performance_report(start:str,end:str) -> list[Dict[str,Any]]:
    conn=connect_db(); cur=conn.cursor(); cur.execute("""
        SELECT e.id,e.employee_no,e.full_name,e.branch,u.username,
               COUNT(s.id) sale_count,COALESCE(SUM(CASE WHEN s.status='completed' THEN s.total ELSE 0 END),0) sales_total,
               COALESCE(SUM(CASE WHEN s.status='refunded' THEN 1 ELSE 0 END),0) refund_count,
               COALESCE(SUM(s.discount_amount),0) discount_total,
               COALESCE(cr.rate_percent,0) commission_rate,COALESCE(cr.target_amount,0) target_amount
        FROM employees e LEFT JOIN users u ON u.id=e.user_id
        LEFT JOIN sales s ON s.created_by=u.username AND DATE(s.created_at)>=? AND DATE(s.created_at)<=?
        LEFT JOIN commission_rules cr ON cr.employee_id=e.id AND cr.active=1
        WHERE e.employment_status='Active'
        GROUP BY e.id,e.employee_no,e.full_name,e.branch,u.username,cr.rate_percent,cr.target_amount
        ORDER BY sales_total DESC""",(start,end)); rows=_rows(cur); conn.close()
    for row in rows:
        row["commission_amount"] = float(row["sales_total"] or 0)*float(row["commission_rate"] or 0)/100 if float(row["sales_total"] or 0)>=float(row["target_amount"] or 0) else 0
    return rows


def list_cash_sessions() -> list[Dict[str,Any]]:
    conn=connect_db(); cur=conn.cursor(); cur.execute("""SELECT c.*,e.employee_no,e.full_name FROM cash_sessions c JOIN employees e ON e.id=c.employee_id ORDER BY c.opened_at DESC"""); rows=_rows(cur); conn.close(); return rows


def open_cash_session(employee_id:int, opening_cash:float, user_id:int, notes:str="") -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("SELECT id FROM cash_sessions WHERE employee_id=? AND status='Open'",(employee_id,))
    if cur.fetchone(): conn.close(); raise ValueError("This employee already has an open cash session")
    cur.execute("INSERT INTO cash_sessions(employee_id,opened_at,opening_cash,notes,opened_by) VALUES(?,CURRENT_TIMESTAMP,?,?,?)",(employee_id,opening_cash,notes,user_id)); conn.commit(); conn.close()


def close_cash_session(session_id:int, actual_cash:float, user_id:int) -> None:
    conn=connect_db(); cur=conn.cursor(); cur.execute("""SELECT c.opening_cash,c.opened_at,u.username FROM cash_sessions c JOIN employees e ON e.id=c.employee_id LEFT JOIN users u ON u.id=e.user_id WHERE c.id=? AND c.status='Open'""",(session_id,)); row=cur.fetchone()
    if not row: conn.close(); raise ValueError("Open cash session not found")
    opening,opened,username=row; cur.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE created_by=? AND created_at>=? AND status='completed' AND LOWER(COALESCE(payment_type,'cash'))='cash'",(username,opened)); sales_cash=float(cur.fetchone()[0] or 0); expected=float(opening or 0)+sales_cash; difference=float(actual_cash)-expected
    cur.execute("UPDATE cash_sessions SET closed_at=CURRENT_TIMESTAMP,expected_cash=?,actual_cash=?,difference=?,status='Closed',closed_by=? WHERE id=?",(expected,actual_cash,difference,user_id,session_id)); conn.commit(); conn.close()


def employee_summary() -> Dict[str,Any]:
    conn=connect_db(); cur=conn.cursor(); result={}
    expiry_sql = "SELECT COUNT(*) FROM employee_documents WHERE expiry_date IS NOT NULL AND CAST(expiry_date AS DATE)<=CURRENT_DATE + INTERVAL '30 days'" if is_postgres_backend() else "SELECT COUNT(*) FROM employee_documents WHERE expiry_date IS NOT NULL AND date(expiry_date)<=date('now','+30 days')"
    for key,sql in (("active","SELECT COUNT(*) FROM employees WHERE employment_status='Active'"),("pending_leave","SELECT COUNT(*) FROM employee_leave WHERE status='Pending'"),("expiring_documents",expiry_sql),("outstanding_advances","SELECT COALESCE(SUM(amount-repaid_amount),0) FROM salary_advances WHERE status='Outstanding'")):
        try: cur.execute(sql); result[key]=cur.fetchone()[0]
        except Exception: result[key]=0
    conn.close(); return result
