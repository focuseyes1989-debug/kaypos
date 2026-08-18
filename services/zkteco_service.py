"""Read-only ZKTeco connector and idempotent attendance importer."""

from collections import defaultdict
from datetime import datetime, timedelta
import sys
from typing import Any, Callable, Dict

from models.database import connect_db
from services.employee_service import ensure_employee_schema, recalculate_attendance_categories
from utils.db_compat import is_postgres_backend

DEFAULT_DEVICE = {
    "device_no": 1,
    "name": "ZKTeco K20",
    "ip_address": "192.168.110.245",
    "port": 4370,
    "comm_key": 0,
}


def ensure_zkteco_schema() -> None:
    ensure_employee_schema()
    conn=connect_db(); cur=conn.cursor(); pk="SERIAL PRIMARY KEY" if is_postgres_backend() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    cur.execute(f"""CREATE TABLE IF NOT EXISTS zkteco_devices (
        id {pk}, device_no INTEGER UNIQUE NOT NULL, name TEXT, ip_address TEXT NOT NULL,
        port INTEGER DEFAULT 4370, comm_key INTEGER DEFAULT 0, serial_no TEXT,
        last_sync_at TIMESTAMP, is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS zkteco_attendance_logs (
        id {pk}, device_id INTEGER NOT NULL, device_user_id TEXT NOT NULL,
        employee_id INTEGER, punch_time TIMESTAMP NOT NULL, status INTEGER,
        punch INTEGER, verification_type INTEGER, imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_valid INTEGER DEFAULT 1, validation_note TEXT,
        UNIQUE(device_id,device_user_id,punch_time,punch),
        FOREIGN KEY(device_id) REFERENCES zkteco_devices(id) ON DELETE CASCADE,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE SET NULL)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS zkteco_employee_mappings (
        id {pk}, device_id INTEGER NOT NULL, employee_id INTEGER NOT NULL,
        device_user_id TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(device_id,device_user_id), UNIQUE(device_id,employee_id),
        FOREIGN KEY(device_id) REFERENCES zkteco_devices(id) ON DELETE CASCADE,
        FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_zkteco_logs_employee_time ON zkteco_attendance_logs(employee_id,punch_time)")
    cur.execute("SELECT id FROM zkteco_devices WHERE device_no=?",(DEFAULT_DEVICE["device_no"],))
    if not cur.fetchone():
        cur.execute("INSERT INTO zkteco_devices(device_no,name,ip_address,port,comm_key,is_active) VALUES(?,?,?,?,?,1)",(
            DEFAULT_DEVICE["device_no"],DEFAULT_DEVICE["name"],DEFAULT_DEVICE["ip_address"],
            DEFAULT_DEVICE["port"],DEFAULT_DEVICE["comm_key"],
        ))
    # Migrate the original single-device mapping without duplicating it.
    cur.execute("SELECT id FROM zkteco_devices WHERE device_no=?",(DEFAULT_DEVICE["device_no"],));default_device_id=cur.fetchone()[0]
    cur.execute("SELECT id,zkteco_user_id FROM employees WHERE zkteco_user_id IS NOT NULL AND zkteco_user_id<>''")
    for employee_id,user_id in cur.fetchall():
        if is_postgres_backend():
            cur.execute("INSERT INTO zkteco_employee_mappings(device_id,employee_id,device_user_id) VALUES(?,?,?) ON CONFLICT(device_id,employee_id) DO NOTHING",(default_device_id,employee_id,str(user_id)))
        else:
            cur.execute("INSERT OR IGNORE INTO zkteco_employee_mappings(device_id,employee_id,device_user_id) VALUES(?,?,?)",(default_device_id,employee_id,str(user_id)))
    conn.commit();conn.close()


def _connect(ip:str,port:int,key:int):
    try:
        from zk import ZK
    except ImportError as exc:
        raise RuntimeError(
            "ZKTeco library could not be loaded.\n"
            f"Import error: {exc}\n"
            f"Python: {sys.executable}\n"
            "Close KAY POS completely, then run:\n"
            f'"{sys.executable}" -m pip install --upgrade pyzk==0.9 future'
        ) from exc
    return ZK(ip,port=port,timeout=10,password=key,force_udp=False,ommit_ping=True).connect()


def sync_employee(device_no:int,ip:str,port:int,comm_key:int,device_user_id:str,employee_no:str) -> Dict[str,Any]:
    ensure_zkteco_schema(); device=None
    try:
        device=_connect(ip,port,comm_key); serial=str(device.get_serialnumber() or ""); device_time=device.get_time(); users={str(u.user_id):u for u in device.get_users()}
        if str(device_user_id) not in users: raise ValueError(f"Device User ID {device_user_id} was not found")
        all_logs=[x for x in device.get_attendance() if str(x.user_id)==str(device_user_id)]
    finally:
        if device:
            try:device.disconnect()
            except Exception:pass
    conn=connect_db();cur=conn.cursor()
    cur.execute("SELECT id FROM zkteco_devices WHERE device_no=?",(device_no,));row=cur.fetchone()
    if row:
        device_id=row[0];cur.execute("UPDATE zkteco_devices SET ip_address=?,port=?,comm_key=?,serial_no=? WHERE id=?",(ip,port,comm_key,serial,device_id))
    else:
        cur.execute("INSERT INTO zkteco_devices(device_no,name,ip_address,port,comm_key,serial_no) VALUES(?,?,?,?,?,?)",(device_no,"ZKTeco K20",ip,port,comm_key,serial));device_id=cur.lastrowid
    cur.execute("SELECT id FROM employees WHERE employee_no=?",(employee_no,));row=cur.fetchone()
    if not row:
        user=users[str(device_user_id)]; valid_times=[x.timestamp for x in all_logs if x.timestamp<=device_time+timedelta(days=1)]; hire=(min(valid_times) if valid_times else device_time).strftime("%Y-%m-%d")
        cur.execute("INSERT INTO employees(employee_no,full_name,hire_date,employment_status,zkteco_user_id) VALUES(?,?,?,?,?)",(employee_no,user.name or employee_no,hire,"Active",str(device_user_id)));employee_id=cur.lastrowid
    else:
        employee_id=row[0];cur.execute("UPDATE employees SET zkteco_user_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(str(device_user_id),employee_id))
    inserted=skipped=invalid=0; affected=set(); cutoff=device_time+timedelta(days=1)
    for log in all_logs:
        valid=log.timestamp<=cutoff; note=None if valid else "Future timestamp beyond device time"
        values=(device_id,str(device_user_id),employee_id,log.timestamp,int(log.status or 0),int(log.punch or 0),None,int(valid),note)
        sql="INSERT INTO zkteco_attendance_logs(device_id,device_user_id,employee_id,punch_time,status,punch,verification_type,is_valid,validation_note) VALUES(?,?,?,?,?,?,?,?,?)"
        sql += " ON CONFLICT(device_id,device_user_id,punch_time,punch) DO NOTHING" if is_postgres_backend() else ""
        if not is_postgres_backend(): sql=sql.replace("INSERT INTO","INSERT OR IGNORE INTO",1)
        cur.execute(sql,values)
        if cur.rowcount:inserted+=1
        else:skipped+=1
        if valid:affected.add(log.timestamp.strftime("%Y-%m-%d"))
        else:invalid+=1
    for day in sorted(affected):
        cur.execute("""SELECT MIN(CASE WHEN punch IN (0,4) THEN punch_time END),MAX(CASE WHEN punch IN (1,5) THEN punch_time END) FROM zkteco_attendance_logs WHERE employee_id=? AND is_valid=1 AND DATE(punch_time)=?""",(employee_id,day));first,last=cur.fetchone();check_in=str(first)[11:16] if first else None;check_out=str(last)[11:16] if last else None
        cur.execute("SELECT id,correction_reason FROM attendance WHERE employee_id=? AND attendance_date=?",(employee_id,day));existing=cur.fetchone()
        if existing and existing[1]:continue
        if existing:cur.execute("UPDATE attendance SET check_in=?,check_out=?,status='Present',notes='ZKTeco K20 sync',updated_at=CURRENT_TIMESTAMP WHERE id=?",(check_in,check_out,existing[0]))
        else:cur.execute("INSERT INTO attendance(employee_id,attendance_date,check_in,check_out,status,notes) VALUES(?,?,?,?,?,?)",(employee_id,day,check_in,check_out,"Present","ZKTeco K20 sync"))
    cur.execute("UPDATE zkteco_devices SET last_sync_at=CURRENT_TIMESTAMP WHERE id=?",(device_id,));conn.commit();conn.close();recalculate_attendance_categories(employee_id)
    return {"employee_id":employee_id,"employee_no":employee_no,"device_user_id":str(device_user_id),"total":len(all_logs),"inserted":inserted,"duplicates":skipped,"invalid":invalid,"attendance_days":len(affected),"serial":serial}


def sync_configured_mappings(
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Dict[str,Any]]:
    ensure_zkteco_schema();conn=connect_db();cur=conn.cursor();cur.execute("""SELECT d.device_no,d.ip_address,d.port,d.comm_key,e.employee_no,m.device_user_id FROM zkteco_employee_mappings m JOIN zkteco_devices d ON d.id=m.device_id JOIN employees e ON e.id=m.employee_id WHERE d.is_active=1 AND e.employment_status='Active' ORDER BY d.device_no,e.id""");rows=cur.fetchall();conn.close()
    if not rows:raise ValueError("No active ZKTeco device/employee mappings are configured")
    results=[];total=len(rows)
    for index,(device_no,ip,port,key,employee_no,user_id) in enumerate(rows):
        if progress_callback:progress_callback(index,total,f"Syncing {employee_no}...")
        results.append(sync_employee(device_no,ip,port,key,user_id,employee_no))
        if progress_callback:progress_callback(index+1,total,f"Synced {employee_no}")
    return results


def list_devices() -> list[Dict[str,Any]]:
    ensure_zkteco_schema();conn=connect_db();cur=conn.cursor();cur.execute("SELECT id,device_no,name,ip_address,port,comm_key,serial_no,last_sync_at,is_active FROM zkteco_devices ORDER BY device_no");rows=_dict_rows(cur);conn.close();return rows


def _dict_rows(cur):
    columns=[x[0] for x in cur.description];return [dict(zip(columns,row)) for row in cur.fetchall()]


def save_device(data:Dict[str,Any],record_id:int|None=None) -> int:
    ensure_zkteco_schema();conn=connect_db();cur=conn.cursor();values=(int(data["device_no"]),data.get("name") or "ZKTeco Device",data["ip_address"],int(data.get("port") or 4370),int(data.get("comm_key") or 0),int(bool(data.get("is_active",True))))
    try:
        if record_id:
            cur.execute("UPDATE zkteco_devices SET device_no=?,name=?,ip_address=?,port=?,comm_key=?,is_active=? WHERE id=?",values+(record_id,));result=record_id
        else:
            cur.execute("INSERT INTO zkteco_devices(device_no,name,ip_address,port,comm_key,is_active) VALUES(?,?,?,?,?,?)",values);result=cur.lastrowid
            if result is None:cur.execute("SELECT id FROM zkteco_devices WHERE device_no=?",(values[0],));result=cur.fetchone()[0]
        conn.commit();return int(result)
    except Exception:conn.rollback();raise
    finally:conn.close()


def test_device(ip:str,port:int,comm_key:int) -> Dict[str,Any]:
    conn=None
    try:
        conn=_connect(ip,int(port),int(comm_key));return {"serial":str(conn.get_serialnumber() or ""),"platform":str(conn.get_platform() or ""),"firmware":str(conn.get_firmware_version() or ""),"time":str(conn.get_time()),"users":len(conn.get_users()),"logs":len(conn.get_attendance())}
    finally:
        if conn:
            try:conn.disconnect()
            except Exception:pass


def list_mappings() -> list[Dict[str,Any]]:
    ensure_zkteco_schema();conn=connect_db();cur=conn.cursor();cur.execute("""SELECT m.id,m.device_id,d.device_no,d.name device_name,m.employee_id,e.employee_no,e.full_name,m.device_user_id FROM zkteco_employee_mappings m JOIN zkteco_devices d ON d.id=m.device_id JOIN employees e ON e.id=m.employee_id ORDER BY d.device_no,e.full_name""");rows=_dict_rows(cur);conn.close();return rows


def save_mapping(device_id:int,employee_id:int,device_user_id:str) -> None:
    ensure_zkteco_schema();conn=connect_db();cur=conn.cursor();cur.execute("SELECT id FROM zkteco_employee_mappings WHERE device_id=? AND employee_id=?",(device_id,employee_id));row=cur.fetchone()
    if row:cur.execute("UPDATE zkteco_employee_mappings SET device_user_id=? WHERE id=?",(str(device_user_id),row[0]))
    else:cur.execute("INSERT INTO zkteco_employee_mappings(device_id,employee_id,device_user_id) VALUES(?,?,?)",(device_id,employee_id,str(device_user_id)))
    conn.commit();conn.close()


def delete_mapping(mapping_id:int) -> None:
    conn=connect_db();cur=conn.cursor();cur.execute("DELETE FROM zkteco_employee_mappings WHERE id=?",(mapping_id,));conn.commit();conn.close()
