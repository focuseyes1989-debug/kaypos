"""PostgreSQL app schema helpers.

The application is still SQLite-compatible, but PostgreSQL mode should be able
to initialize the full POS schema instead of only the Restaurant Mode pilot.
"""

import hashlib
import os

from utils.db_compat import ensure_column, is_postgres_backend, quote_identifier


def ensure_postgres_app_schema(cursor):
    if not is_postgres_backend():
        raise RuntimeError("PostgreSQL schema can only run with ZAY_POS_DB_BACKEND=postgres.")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            description TEXT,
            sold_by TEXT DEFAULT 'Each',
            price DOUBLE PRECISION DEFAULT 0,
            cost DOUBLE PRECISION DEFAULT 0,
            sku TEXT,
            barcode TEXT,
            stock DOUBLE PRECISION DEFAULT 0,
            expire_date TEXT,
            low_stock DOUBLE PRECISION DEFAULT 0,
            image TEXT,
            image_data BYTEA,
            image_mime TEXT,
            image_filename TEXT,
            supplier_id INTEGER,
            unit TEXT,
            base_unit TEXT DEFAULT 'pcs',
            pack_unit TEXT DEFAULT '',
            pack_size INTEGER DEFAULT 1,
            restaurant_modifiers TEXT,
            warehouse TEXT,
            batch_no TEXT,
            manufacture_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_favourite INTEGER DEFAULT 0,
            category_id INTEGER
        )
    """)
    _ensure_product_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            total_visit INTEGER DEFAULT 0,
            total_spent DOUBLE PRECISION DEFAULT 0,
            points INTEGER DEFAULT 0,
            credit_limit DOUBLE PRECISION DEFAULT 0,
            current_balance DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id SERIAL PRIMARY KEY,
            invoice_no TEXT UNIQUE,
            total DOUBLE PRECISION DEFAULT 0,
            payment DOUBLE PRECISION DEFAULT 0,
            change_amount DOUBLE PRECISION DEFAULT 0,
            customer_id INTEGER,
            status TEXT DEFAULT 'completed',
            payment_type TEXT,
            discount_amount DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cogs DOUBLE PRECISION DEFAULT 0,
            gross_profit DOUBLE PRECISION DEFAULT 0,
            net_profit DOUBLE PRECISION DEFAULT 0
        )
    """)
    ensure_column(cursor, "sales", "created_by", "TEXT")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id SERIAL PRIMARY KEY,
            sale_id INTEGER REFERENCES sales(id) ON DELETE CASCADE,
            product_id INTEGER,
            product_name TEXT,
            qty DOUBLE PRECISION DEFAULT 0,
            price DOUBLE PRECISION DEFAULT 0,
            total DOUBLE PRECISION DEFAULT 0,
            cost DOUBLE PRECISION DEFAULT 0,
            variant_id INTEGER,
            location_id INTEGER,
            location TEXT,
            batch_no TEXT,
            expire_date TEXT,
            wholesale_regular_price DOUBLE PRECISION DEFAULT 0,
            wholesale_savings DOUBLE PRECISION DEFAULT 0,
            wholesale_tier_min_qty INTEGER,
            wholesale_unit_label TEXT
        )
    """)
    _ensure_sale_item_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT,
            description TEXT,
            parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            sort_order INTEGER DEFAULT 0,
            color TEXT DEFAULT '#6c5ce7',
            icon TEXT DEFAULT '',
            image_path TEXT,
            status TEXT DEFAULT 'active',
            code TEXT,
            notes TEXT,
            is_system INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_groups (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            sort_order INTEGER DEFAULT 0,
            icon TEXT DEFAULT '',
            color TEXT DEFAULT '#6c5ce7',
            is_favorite INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_category_group_columns(cursor)
    _ensure_category_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_types (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_discounts (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            discount_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            note TEXT,
            discount_type TEXT DEFAULT 'percentage',
            manual_price DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_product_discount_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            size TEXT,
            color TEXT,
            sku TEXT,
            barcode TEXT,
            price DOUBLE PRECISION DEFAULT 0,
            cost DOUBLE PRECISION DEFAULT 0,
            stock INTEGER DEFAULT 0,
            low_stock INTEGER DEFAULT 0,
            image TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_product_variant_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_locations (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            quantity DOUBLE PRECISION DEFAULT 0,
            location TEXT DEFAULT '',
            batch_no TEXT DEFAULT '',
            expire_date TEXT,
            manufacture_date TEXT,
            expiry_discount_enabled INTEGER DEFAULT 0,
            expiry_discount_percent DOUBLE PRECISION DEFAULT 0,
            expiry_discount_start_date TEXT,
            expiry_discount_end_date TEXT,
            clearance_note TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(product_id, location, batch_no, expire_date)
        )
    """)
    _ensure_product_location_columns(cursor)
    _normalize_product_location_types(cursor)
    _ensure_product_location_constraints(cursor)
    _ensure_supplier_inventory_tables(cursor)
    _ensure_expense_tables(cursor)
    _ensure_supporting_tables(cursor)
    _ensure_credit_tables(cursor)
    _ensure_user_tables(cursor)
    _ensure_employee_tables(cursor)
    _ensure_audit_hold_tables(cursor)
    _ensure_restaurant_tables(cursor)
    _ensure_indexes(cursor)
    _ensure_default_users(cursor)


def ensure_postgres_restaurant_pilot_schema(cursor):
    """Backward-compatible alias for older startup/smoke-test code."""
    ensure_postgres_app_schema(cursor)


def _ensure_employee_tables(cursor):
    cursor.execute("""CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY, employee_no TEXT UNIQUE NOT NULL, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
        full_name TEXT NOT NULL, phone TEXT, address TEXT, date_of_birth TEXT, national_id TEXT, photo_path TEXT,
        hire_date TEXT NOT NULL, position TEXT, department TEXT, branch TEXT, employment_status TEXT DEFAULT 'Active', zkteco_user_id TEXT,
        emergency_contact_name TEXT, emergency_contact_phone TEXT, notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    ensure_column(cursor, "employees", "zkteco_user_id", "TEXT")
    cursor.execute("""CREATE TABLE IF NOT EXISTS shifts (id SERIAL PRIMARY KEY,name TEXT UNIQUE NOT NULL,start_time TEXT NOT NULL,end_time TEXT NOT NULL,break_minutes INTEGER DEFAULT 0,is_overnight INTEGER DEFAULT 0,is_active INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS employee_shifts (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,shift_id INTEGER REFERENCES shifts(id) ON DELETE CASCADE,effective_from TEXT NOT NULL,effective_to TEXT,weekly_off_days TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS attendance (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,attendance_date TEXT NOT NULL,check_in TEXT,check_out TEXT,status TEXT DEFAULT 'Present',late_minutes INTEGER DEFAULT 0,notes TEXT,corrected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,correction_reason TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(employee_id,attendance_date))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS payrolls (id SERIAL PRIMARY KEY,payroll_no TEXT UNIQUE NOT NULL,employee_id INTEGER REFERENCES employees(id) ON DELETE RESTRICT,period_month TEXT NOT NULL,basic_salary DOUBLE PRECISION DEFAULT 0,allowance DOUBLE PRECISION DEFAULT 0,overtime_amount DOUBLE PRECISION DEFAULT 0,bonus DOUBLE PRECISION DEFAULT 0,late_deduction DOUBLE PRECISION DEFAULT 0,absence_deduction DOUBLE PRECISION DEFAULT 0,advance_deduction DOUBLE PRECISION DEFAULT 0,other_deduction DOUBLE PRECISION DEFAULT 0,net_salary DOUBLE PRECISION DEFAULT 0,status TEXT DEFAULT 'Draft',paid_date TEXT,payment_method TEXT,expense_id INTEGER REFERENCES expenses(id) ON DELETE SET NULL,notes TEXT,created_by INTEGER,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(employee_id,period_month))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS employee_leave (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,leave_type TEXT NOT NULL,start_date TEXT NOT NULL,end_date TEXT NOT NULL,days DOUBLE PRECISION DEFAULT 1,reason TEXT,status TEXT DEFAULT 'Pending',reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,reviewed_at TIMESTAMP,review_notes TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS employee_documents (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,document_type TEXT NOT NULL,document_no TEXT,file_path TEXT,issued_date TEXT,expiry_date TEXT,notes TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS salary_advances (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE RESTRICT,advance_date TEXT NOT NULL,amount DOUBLE PRECISION NOT NULL,repaid_amount DOUBLE PRECISION DEFAULT 0,status TEXT DEFAULT 'Outstanding',notes TEXT,created_by INTEGER,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS commission_rules (id SERIAL PRIMARY KEY,employee_id INTEGER UNIQUE REFERENCES employees(id) ON DELETE CASCADE,rate_percent DOUBLE PRECISION DEFAULT 0,target_amount DOUBLE PRECISION DEFAULT 0,active INTEGER DEFAULT 1,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS cash_sessions (id SERIAL PRIMARY KEY,employee_id INTEGER REFERENCES employees(id) ON DELETE RESTRICT,opened_at TIMESTAMP NOT NULL,opening_cash DOUBLE PRECISION DEFAULT 0,closed_at TIMESTAMP,expected_cash DOUBLE PRECISION,actual_cash DOUBLE PRECISION,difference DOUBLE PRECISION,status TEXT DEFAULT 'Open',notes TEXT,opened_by INTEGER,closed_by INTEGER)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS zkteco_devices (id SERIAL PRIMARY KEY,device_no INTEGER UNIQUE NOT NULL,name TEXT,ip_address TEXT NOT NULL,port INTEGER DEFAULT 4370,comm_key INTEGER DEFAULT 0,serial_no TEXT,last_sync_at TIMESTAMP,is_active INTEGER DEFAULT 1,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS zkteco_attendance_logs (id SERIAL PRIMARY KEY,device_id INTEGER REFERENCES zkteco_devices(id) ON DELETE CASCADE,device_user_id TEXT NOT NULL,employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,punch_time TIMESTAMP NOT NULL,status INTEGER,punch INTEGER,verification_type INTEGER,imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,is_valid INTEGER DEFAULT 1,validation_note TEXT,UNIQUE(device_id,device_user_id,punch_time,punch))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS zkteco_employee_mappings (id SERIAL PRIMARY KEY,device_id INTEGER REFERENCES zkteco_devices(id) ON DELETE CASCADE,employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,device_user_id TEXT NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(device_id,device_user_id),UNIQUE(device_id,employee_id))""")


def _ensure_sale_item_columns(cursor):
    columns = {
        "product_id": "INTEGER",
        "cost": "DOUBLE PRECISION DEFAULT 0",
        "variant_id": "INTEGER",
        "location_id": "INTEGER",
        "location": "TEXT",
        "batch_no": "TEXT",
        "expire_date": "TEXT",
        "wholesale_regular_price": "DOUBLE PRECISION DEFAULT 0",
        "wholesale_savings": "DOUBLE PRECISION DEFAULT 0",
        "wholesale_tier_min_qty": "INTEGER",
        "wholesale_unit_label": "TEXT",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "sale_items", column, definition)


def _ensure_product_columns(cursor):
    columns = {
        "category": "TEXT",
        "description": "TEXT",
        "sold_by": "TEXT DEFAULT 'Each'",
        "price": "DOUBLE PRECISION DEFAULT 0",
        "cost": "DOUBLE PRECISION DEFAULT 0",
        "sku": "TEXT",
        "barcode": "TEXT",
        "stock": "DOUBLE PRECISION DEFAULT 0",
        "expire_date": "TEXT",
        "low_stock": "DOUBLE PRECISION DEFAULT 0",
        "image": "TEXT",
        "image_data": "BYTEA",
        "image_mime": "TEXT",
        "image_filename": "TEXT",
        "supplier_id": "INTEGER",
        "unit": "TEXT",
        "base_unit": "TEXT DEFAULT 'pcs'",
        "pack_unit": "TEXT DEFAULT ''",
        "pack_size": "INTEGER DEFAULT 1",
        "restaurant_modifiers": "TEXT",
        "warehouse": "TEXT",
        "batch_no": "TEXT",
        "manufacture_date": "TEXT",
        "last_updated": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "is_favourite": "INTEGER DEFAULT 0",
        "category_id": "INTEGER",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "products", column, definition)


def _ensure_category_columns(cursor):
    columns = {
        "slug": "TEXT",
        "description": "TEXT",
        "parent_id": "INTEGER",
        "sort_order": "INTEGER DEFAULT 0",
        "color": "TEXT DEFAULT '#6c5ce7'",
        "icon": "TEXT DEFAULT ''",
        "image_path": "TEXT",
        "status": "TEXT DEFAULT 'active'",
        "code": "TEXT",
        "notes": "TEXT",
        "is_system": "INTEGER DEFAULT 0",
        "is_favorite": "INTEGER DEFAULT 0",
        "group_id": "INTEGER",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "categories", column, definition)


def _ensure_category_group_columns(cursor):
    columns = {
        "description": "TEXT",
        "sort_order": "INTEGER DEFAULT 0",
        "icon": "TEXT DEFAULT ''",
        "color": "TEXT DEFAULT '#6c5ce7'",
        "is_favorite": "INTEGER DEFAULT 0",
        "is_active": "INTEGER DEFAULT 1",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "category_groups", column, definition)


def _ensure_product_discount_columns(cursor):
    columns = {
        "discount_percent": "DOUBLE PRECISION NOT NULL DEFAULT 0",
        "start_date": "TEXT NOT NULL DEFAULT ''",
        "end_date": "TEXT NOT NULL DEFAULT ''",
        "active": "INTEGER NOT NULL DEFAULT 1",
        "note": "TEXT",
        "discount_type": "TEXT DEFAULT 'percentage'",
        "manual_price": "DOUBLE PRECISION DEFAULT 0",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "product_discounts", column, definition)


def _ensure_product_variant_columns(cursor):
    columns = {
        "product_id": "INTEGER",
        "size": "TEXT",
        "color": "TEXT",
        "sku": "TEXT",
        "barcode": "TEXT",
        "price": "DOUBLE PRECISION DEFAULT 0",
        "cost": "DOUBLE PRECISION DEFAULT 0",
        "stock": "INTEGER DEFAULT 0",
        "low_stock": "INTEGER DEFAULT 0",
        "image": "TEXT",
        "active": "INTEGER DEFAULT 1",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "product_variants", column, definition)


def _ensure_product_location_columns(cursor):
    columns = {
        "quantity": "DOUBLE PRECISION DEFAULT 0",
        "location": "TEXT DEFAULT ''",
        "batch_no": "TEXT DEFAULT ''",
        "expire_date": "TEXT",
        "manufacture_date": "TEXT",
        "expiry_discount_enabled": "INTEGER DEFAULT 0",
        "expiry_discount_percent": "DOUBLE PRECISION DEFAULT 0",
        "expiry_discount_start_date": "TEXT",
        "expiry_discount_end_date": "TEXT",
        "clearance_note": "TEXT",
        "last_updated": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "product_locations", column, definition)


def _normalize_product_location_types(cursor):
    cursor.execute("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = CURRENT_SCHEMA()
          AND table_name = 'product_locations'
          AND column_name = 'expire_date'
    """)
    row = cursor.fetchone()
    if row and row[0] != "text":
        cursor.execute("""
            ALTER TABLE product_locations
            ALTER COLUMN expire_date TYPE TEXT
            USING COALESCE(expire_date::text, '')
        """)


def _ensure_product_location_constraints(cursor):
    cursor.execute("""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'product_locations'::regclass
          AND contype = 'u'
    """)
    for constraint_name, definition in cursor.fetchall():
        if definition == "UNIQUE (product_id, location)":
            cursor.execute(
                f"ALTER TABLE product_locations DROP CONSTRAINT {quote_identifier(constraint_name)}"
            )


def _ensure_supplier_inventory_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            company_name TEXT,
            tax_number TEXT,
            website TEXT,
            payment_terms TEXT,
            bank_account TEXT,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            type TEXT,
            quantity DOUBLE PRECISION,
            old_stock DOUBLE PRECISION,
            new_stock DOUBLE PRECISION,
            reason TEXT,
            reference TEXT,
            created_by TEXT,
            notes TEXT,
            supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            location TEXT,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id SERIAL PRIMARY KEY,
            po_no TEXT UNIQUE,
            supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            order_date TEXT,
            total_amount DOUBLE PRECISION DEFAULT 0,
            status TEXT DEFAULT 'pending',
            discount DOUBLE PRECISION DEFAULT 0,
            tax DOUBLE PRECISION DEFAULT 0,
            payment_status TEXT DEFAULT 'Unpaid',
            received_by TEXT,
            invoice_attachment TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id SERIAL PRIMARY KEY,
            po_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            quantity DOUBLE PRECISION DEFAULT 0,
            unit_price DOUBLE PRECISION DEFAULT 0,
            total DOUBLE PRECISION DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_payments (
            id SERIAL PRIMARY KEY,
            supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
            amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            payment_date TEXT NOT NULL,
            reference_no TEXT,
            payment_type TEXT DEFAULT 'Cash',
            notes TEXT,
            purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for table, columns in {
        "suppliers": {
            "contact_person": "TEXT",
            "phone": "TEXT",
            "email": "TEXT",
            "address": "TEXT",
            "company_name": "TEXT",
            "tax_number": "TEXT",
            "website": "TEXT",
            "payment_terms": "TEXT",
            "bank_account": "TEXT",
            "status": "TEXT DEFAULT 'Active'",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "stock_movements": {
            "product_id": "INTEGER",
            "type": "TEXT",
            "quantity": "DOUBLE PRECISION",
            "old_stock": "DOUBLE PRECISION",
            "new_stock": "DOUBLE PRECISION",
            "reason": "TEXT",
            "reference": "TEXT",
            "created_by": "TEXT",
            "notes": "TEXT",
            "supplier_id": "INTEGER",
            "location": "TEXT",
            "customer_id": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "purchase_orders": {
            "po_no": "TEXT",
            "supplier_id": "INTEGER",
            "order_date": "TEXT",
            "total_amount": "DOUBLE PRECISION DEFAULT 0",
            "status": "TEXT DEFAULT 'pending'",
            "discount": "DOUBLE PRECISION DEFAULT 0",
            "tax": "DOUBLE PRECISION DEFAULT 0",
            "payment_status": "TEXT DEFAULT 'Unpaid'",
            "received_by": "TEXT",
            "invoice_attachment": "TEXT",
            "notes": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "purchase_order_items": {
            "po_id": "INTEGER",
            "product_id": "INTEGER",
            "quantity": "DOUBLE PRECISION DEFAULT 0",
            "unit_price": "DOUBLE PRECISION DEFAULT 0",
            "total": "DOUBLE PRECISION DEFAULT 0",
        },
        "supplier_payments": {
            "supplier_id": "INTEGER",
            "amount": "DOUBLE PRECISION DEFAULT 0",
            "payment_date": "TEXT",
            "reference_no": "TEXT",
            "payment_type": "TEXT DEFAULT 'Cash'",
            "notes": "TEXT",
            "purchase_order_id": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
    }.items():
        for column, definition in columns.items():
            ensure_column(cursor, table, column, definition)


def _ensure_expense_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_expense_category_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            expense_no TEXT UNIQUE,
            category TEXT NOT NULL,
            description TEXT,
            amount DOUBLE PRECISION DEFAULT 0,
            expense_date TEXT,
            payment_method TEXT,
            reference_no TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image TEXT
        )
    """)
    _ensure_expense_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_budgets (
            id SERIAL PRIMARY KEY,
            category TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            budget_amount DOUBLE PRECISION DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_expense_budget_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_notification_settings (
            id SERIAL PRIMARY KEY,
            enable_notifications INTEGER DEFAULT 1,
            warning_threshold INTEGER DEFAULT 80,
            check_frequency TEXT DEFAULT 'daily',
            last_checked TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_expense_notification_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_alerts_log (
            id SERIAL PRIMARY KEY,
            category TEXT,
            month INTEGER,
            year INTEGER,
            budget_amount DOUBLE PRECISION DEFAULT 0,
            actual_amount DOUBLE PRECISION DEFAULT 0,
            used_percentage DOUBLE PRECISION DEFAULT 0,
            alert_type TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_expense_alert_columns(cursor)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_attachments (
            id SERIAL PRIMARY KEY,
            expense_id INTEGER REFERENCES expenses(id) ON DELETE CASCADE,
            filename TEXT,
            file_path TEXT,
            file_size INTEGER DEFAULT 0,
            mime_type TEXT,
            uploaded_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _ensure_expense_attachment_columns(cursor)


def _ensure_expense_category_columns(cursor):
    columns = {
        "name": "TEXT",
        "description": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expense_categories", column, definition)


def _ensure_expense_columns(cursor):
    columns = {
        "expense_no": "TEXT",
        "category": "TEXT",
        "description": "TEXT",
        "amount": "DOUBLE PRECISION DEFAULT 0",
        "expense_date": "TEXT",
        "payment_method": "TEXT",
        "reference_no": "TEXT",
        "notes": "TEXT",
        "created_by": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "image": "TEXT",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expenses", column, definition)


def _ensure_expense_budget_columns(cursor):
    columns = {
        "category": "TEXT",
        "month": "INTEGER",
        "year": "INTEGER",
        "budget_amount": "DOUBLE PRECISION DEFAULT 0",
        "notes": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expense_budgets", column, definition)


def _ensure_expense_notification_columns(cursor):
    columns = {
        "enable_notifications": "INTEGER DEFAULT 1",
        "warning_threshold": "INTEGER DEFAULT 80",
        "check_frequency": "TEXT DEFAULT 'daily'",
        "last_checked": "TIMESTAMP",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expense_notification_settings", column, definition)


def _ensure_expense_alert_columns(cursor):
    columns = {
        "category": "TEXT",
        "month": "INTEGER",
        "year": "INTEGER",
        "budget_amount": "DOUBLE PRECISION DEFAULT 0",
        "actual_amount": "DOUBLE PRECISION DEFAULT 0",
        "used_percentage": "DOUBLE PRECISION DEFAULT 0",
        "alert_type": "TEXT",
        "message": "TEXT",
        "is_read": "INTEGER DEFAULT 0",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expense_alerts_log", column, definition)


def _ensure_expense_attachment_columns(cursor):
    columns = {
        "expense_id": "INTEGER",
        "filename": "TEXT",
        "file_path": "TEXT",
        "file_size": "INTEGER DEFAULT 0",
        "mime_type": "TEXT",
        "uploaded_by": "TEXT",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }
    for column, definition in columns.items():
        ensure_column(cursor, "expense_attachments", column, definition)


def _ensure_supporting_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_drawer (
            id SERIAL PRIMARY KEY,
            is_active INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            sale_id INTEGER REFERENCES sales(id) ON DELETE SET NULL,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            payment_type TEXT,
            amount DOUBLE PRECISION DEFAULT 0,
            cash_drawer_id INTEGER,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_adjustments (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            credit_sale_id INTEGER,
            amount DOUBLE PRECISION DEFAULT 0,
            adjustment_type TEXT,
            reason TEXT,
            reference_no TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id SERIAL PRIMARY KEY,
            credit_sale_id INTEGER,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            amount DOUBLE PRECISION DEFAULT 0,
            transaction_type TEXT,
            reference_no TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            type TEXT,
            description TEXT,
            payment_id INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expiry_alerts_log (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
            product_name TEXT,
            location TEXT,
            batch_no TEXT,
            expire_date TEXT,
            quantity INTEGER DEFAULT 0,
            alert_type TEXT,
            message TEXT,
            sale_id INTEGER REFERENCES sales(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_resolved INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_activity_log (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            action TEXT,
            details TEXT,
            user_id INTEGER,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_stats (
            category_id INTEGER PRIMARY KEY,
            product_count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_metadata (
            id SERIAL PRIMARY KEY,
            app_version TEXT,
            db_version TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migrations (
            id SERIAL PRIMARY KEY,
            version TEXT,
            name TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id SERIAL PRIMARY KEY,
            version TEXT,
            name TEXT,
            description TEXT,
            status TEXT,
            applied_at TIMESTAMP,
            rolled_back_at TIMESTAMP,
            executed_by TEXT,
            execution_time DOUBLE PRECISION DEFAULT 0,
            error_message TEXT
        )
    """)
    for table, columns in {
        "locations": {"name": "TEXT", "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"},
        "cash_drawer": {"is_active": "INTEGER DEFAULT 0"},
        "payments": {
            "sale_id": "INTEGER",
            "customer_id": "INTEGER",
            "payment_type": "TEXT",
            "amount": "DOUBLE PRECISION DEFAULT 0",
            "cash_drawer_id": "INTEGER",
            "payment_date": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "credit_adjustments": {
            "customer_id": "INTEGER",
            "credit_sale_id": "INTEGER",
            "amount": "DOUBLE PRECISION DEFAULT 0",
            "adjustment_type": "TEXT",
            "reason": "TEXT",
            "reference_no": "TEXT",
            "created_by": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "credit_transactions": {
            "credit_sale_id": "INTEGER",
            "customer_id": "INTEGER",
            "amount": "DOUBLE PRECISION DEFAULT 0",
            "transaction_type": "TEXT",
            "reference_no": "TEXT",
            "notes": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "type": "TEXT",
            "description": "TEXT",
            "payment_id": "INTEGER",
        },
        "expiry_alerts_log": {
            "product_id": "INTEGER",
            "product_name": "TEXT",
            "location": "TEXT",
            "batch_no": "TEXT",
            "expire_date": "TEXT",
            "quantity": "INTEGER DEFAULT 0",
            "alert_type": "TEXT",
            "message": "TEXT",
            "sale_id": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "is_resolved": "INTEGER DEFAULT 0",
        },
        "category_activity_log": {
            "category_id": "INTEGER",
            "action": "TEXT",
            "details": "TEXT",
            "user_id": "INTEGER",
            "username": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "category_stats": {
            "category_id": "INTEGER",
            "product_count": "INTEGER DEFAULT 0",
            "last_updated": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
        "app_metadata": {
            "app_version": "TEXT",
            "db_version": "TEXT",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "notes": "TEXT",
        },
        "migrations": {
            "version": "TEXT",
            "name": "TEXT",
            "applied_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "description": "TEXT",
        },
        "migration_history": {
            "version": "TEXT",
            "name": "TEXT",
            "description": "TEXT",
            "status": "TEXT",
            "applied_at": "TIMESTAMP",
            "rolled_back_at": "TIMESTAMP",
            "executed_by": "TEXT",
            "execution_time": "DOUBLE PRECISION DEFAULT 0",
            "error_message": "TEXT",
        },
    }.items():
        for column, definition in columns.items():
            ensure_column(cursor, table, column, definition)


def _ensure_credit_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_sales (
            id SERIAL PRIMARY KEY,
            invoice_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            total_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            paid_amount DOUBLE PRECISION DEFAULT 0,
            balance_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            sale_date TEXT NOT NULL,
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            sale_id INTEGER REFERENCES sales(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            refunded_at TIMESTAMP,
            refund_reason TEXT,
            refund_type TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_payments (
            id SERIAL PRIMARY KEY,
            credit_sale_id INTEGER NOT NULL REFERENCES credit_sales(id) ON DELETE CASCADE,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
            amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            payment_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            reference_no TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for table, columns in {
        "credit_sales": {
            "invoice_no": "TEXT",
            "customer_id": "INTEGER",
            "total_amount": "DOUBLE PRECISION DEFAULT 0",
            "paid_amount": "DOUBLE PRECISION DEFAULT 0",
            "balance_amount": "DOUBLE PRECISION DEFAULT 0",
            "sale_date": "TEXT",
            "due_date": "TEXT",
            "status": "TEXT DEFAULT 'pending'",
            "notes": "TEXT",
            "sale_id": "INTEGER",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP",
            "refunded_at": "TIMESTAMP",
            "refund_reason": "TEXT",
            "refund_type": "TEXT",
        },
        "credit_payments": {
            "credit_sale_id": "INTEGER",
            "customer_id": "INTEGER",
            "amount": "DOUBLE PRECISION DEFAULT 0",
            "payment_date": "TEXT",
            "payment_method": "TEXT DEFAULT 'Cash'",
            "reference_no": "TEXT",
            "note": "TEXT",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        },
    }.items():
        for column, definition in columns.items():
            ensure_column(cursor, table, column, definition)


def _ensure_user_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Cashier',
            full_name TEXT,
            salt TEXT,
            force_password_change INTEGER DEFAULT 0,
            permissions TEXT,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            permissions TEXT,
            is_system INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _ensure_audit_hold_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_points_log (
            id SERIAL PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            points INTEGER NOT NULL,
            type TEXT NOT NULL,
            reference TEXT,
            expiry_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS held_sales (
            id SERIAL PRIMARY KEY,
            hold_no TEXT UNIQUE,
            cart_json TEXT NOT NULL,
            customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
            customer_name TEXT,
            payment_type TEXT,
            note TEXT,
            total_amount DOUBLE PRECISION DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _ensure_restaurant_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            id SERIAL PRIMARY KEY,
            table_no TEXT UNIQUE NOT NULL,
            display_name TEXT,
            seats INTEGER DEFAULT 4,
            status TEXT DEFAULT 'available',
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_orders (
            id SERIAL PRIMARY KEY,
            order_no TEXT UNIQUE NOT NULL,
            table_id INTEGER REFERENCES restaurant_tables(id) ON DELETE SET NULL,
            order_type TEXT DEFAULT 'Dine-in',
            status TEXT DEFAULT 'open',
            kitchen_status TEXT DEFAULT 'draft',
            cart_json TEXT NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            note TEXT,
            total_amount DOUBLE PRECISION DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_to_kitchen_at TIMESTAMP,
            settled_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            sale_id INTEGER REFERENCES sales(id) ON DELETE SET NULL,
            invoice_no TEXT,
            settled_total DOUBLE PRECISION DEFAULT 0,
            payment_amount DOUBLE PRECISION DEFAULT 0,
            change_amount DOUBLE PRECISION DEFAULT 0,
            payment_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES restaurant_orders(id) ON DELETE CASCADE,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            quantity DOUBLE PRECISION DEFAULT 0,
            unit_price DOUBLE PRECISION DEFAULT 0,
            base_price DOUBLE PRECISION DEFAULT 0,
            line_total DOUBLE PRECISION DEFAULT 0,
            note TEXT,
            line_id TEXT,
            status TEXT DEFAULT 'active',
            kitchen_status TEXT DEFAULT 'draft',
            sent_quantity DOUBLE PRECISION DEFAULT 0,
            cancelled_quantity DOUBLE PRECISION DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_order_modifiers (
            id SERIAL PRIMARY KEY,
            order_item_id INTEGER NOT NULL REFERENCES restaurant_order_items(id) ON DELETE CASCADE,
            group_name TEXT,
            modifier_name TEXT NOT NULL,
            modifier_type TEXT DEFAULT 'note',
            price_delta DOUBLE PRECISION DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_tickets (
            id SERIAL PRIMARY KEY,
            ticket_no TEXT UNIQUE NOT NULL,
            order_id INTEGER NOT NULL REFERENCES restaurant_orders(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'sent',
            ticket_signature TEXT NOT NULL,
            printed INTEGER DEFAULT 0,
            note TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_ticket_items (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL REFERENCES restaurant_kitchen_tickets(id) ON DELETE CASCADE,
            order_item_id INTEGER REFERENCES restaurant_order_items(id) ON DELETE SET NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            modifier_summary TEXT,
            quantity DOUBLE PRECISION DEFAULT 0,
            note TEXT,
            status TEXT DEFAULT 'sent',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            preparing_at TIMESTAMP,
            ready_at TIMESTAMP,
            served_at TIMESTAMP,
            cancelled_at TIMESTAMP
        )
    """)


def _ensure_indexes(cursor):
    statements = (
        "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)",
        "CREATE INDEX IF NOT EXISTS idx_products_sold_by ON products(sold_by)",
        "CREATE INDEX IF NOT EXISTS idx_product_discounts_product ON product_discounts(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_product_discounts_dates ON product_discounts(start_date, end_date)",
        "CREATE INDEX IF NOT EXISTS idx_product_variants_product ON product_variants(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_product_variants_barcode ON product_variants(barcode)",
        "CREATE INDEX IF NOT EXISTS idx_product_variants_sku ON product_variants(sku)",
        "CREATE INDEX IF NOT EXISTS idx_product_locations_product ON product_locations(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_product_locations_expire ON product_locations(expire_date)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date)",
        "CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)",
        "CREATE INDEX IF NOT EXISTS idx_expense_categories_name ON expense_categories(name)",
        "CREATE INDEX IF NOT EXISTS idx_expense_budgets_category ON expense_budgets(category, year, month)",
        "CREATE INDEX IF NOT EXISTS idx_expense_alerts_read ON expense_alerts_log(is_read)",
        "CREATE INDEX IF NOT EXISTS idx_expense_alerts_created ON expense_alerts_log(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_expense_attachments_expense ON expense_attachments(expense_id)",
        "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)",
        "CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_stock_movements_created ON stock_movements(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_order_items_po ON purchase_order_items(po_id)",
        "CREATE INDEX IF NOT EXISTS idx_purchase_order_items_product ON purchase_order_items(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id)",
        "CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name)",
        "CREATE INDEX IF NOT EXISTS idx_payments_sale ON payments(sale_id)",
        "CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_status ON credit_sales(customer_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_credit_sales_status_date ON credit_sales(status, due_date)",
        "CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_balance_due ON credit_sales(customer_id, balance_amount, due_date)",
        "CREATE INDEX IF NOT EXISTS idx_credit_payments_customer_date ON credit_payments(customer_id, payment_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_credit_adjustments_customer ON credit_adjustments(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_credit_transactions_customer ON credit_transactions(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(transaction_type)",
        "CREATE INDEX IF NOT EXISTS idx_expiry_alerts_product ON expiry_alerts_log(product_id)",
        "CREATE INDEX IF NOT EXISTS idx_expiry_alerts_resolved ON expiry_alerts_log(is_resolved)",
        "CREATE INDEX IF NOT EXISTS idx_category_activity_category ON category_activity_log(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_sales_invoice_no ON sales(invoice_no)",
        "CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_user_roles_name ON user_roles(name)",
        "CREATE INDEX IF NOT EXISTS idx_customer_points_log_customer ON customer_points_log(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_activity_log_user ON user_activity_log(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_held_sales_hold_no ON held_sales(hold_no)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_orders_table ON restaurant_orders(table_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_orders_status ON restaurant_orders(status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_orders_type_status ON restaurant_orders(order_type, status, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_order ON restaurant_order_items(order_id, sort_order)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_status ON restaurant_order_items(order_id, status, kitchen_status)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_order_items_line ON restaurant_order_items(order_id, line_id)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_order_modifiers_item ON restaurant_order_modifiers(order_item_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_signature ON restaurant_kitchen_tickets(order_id, ticket_signature)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_tickets_status ON restaurant_kitchen_tickets(status, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_ticket ON restaurant_kitchen_ticket_items(ticket_id, sort_order)",
        "CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_status ON restaurant_kitchen_ticket_items(ticket_id, status)",
    )
    for statement in statements:
        cursor.execute(statement)


def _ensure_default_users(cursor):
    default_roles = (
        (
            "Admin",
            "Full access to every page and action",
            "dashboard,sales,create_sale,edit_sale,delete_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,delete_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,users,add_user,edit_user,delete_user,settings,edit_settings,backup,restore,factory_reset",
            1,
        ),
        (
            "Manager",
            "Manage daily operations without user deletion, restore, or factory reset",
            "dashboard,sales,create_sale,edit_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,settings,backup",
            0,
        ),
        (
            "Cashier",
            "Process sales, print receipts, refund receipts, and manage sale customers",
            "sales,create_sale,receipts,print_receipt,refund_receipt,customers,add_customer,credit,credit_sale,payment_collection",
            0,
        ),
        (
            "Viewer",
            "Read-only access to dashboards, lists, receipts, reports, and credit",
            "dashboard,sales_summary,products,inventory,receipts,customers,reports,credit",
            0,
        ),
    )
    for name, description, permissions, is_system in default_roles:
        cursor.execute("""
            INSERT INTO user_roles (name, description, permissions, is_system)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (name) DO UPDATE
            SET description = EXCLUDED.description,
                permissions = EXCLUDED.permissions,
                is_system = EXCLUDED.is_system
        """, (name, description, permissions, is_system))

    cursor.execute("SELECT id, role FROM users WHERE username = ?", ("admin",))
    admin = cursor.fetchone()
    if admin:
        if admin[1] != "Admin":
            cursor.execute("UPDATE users SET role = ? WHERE username = ?", ("Admin", "admin"))
        return

    salt_bytes = os.urandom(32)
    salt_hex = salt_bytes.hex()
    password_hash = hashlib.pbkdf2_hmac("sha256", "admin".encode(), salt_bytes, 100000).hex()
    cursor.execute("""
        INSERT INTO users (username, password_hash, role, full_name, salt, force_password_change, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (username) DO NOTHING
    """, ("admin", password_hash, "Admin", "Administrator", salt_hex, 0, 1))
