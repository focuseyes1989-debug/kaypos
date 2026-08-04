# models/database.py
import sqlite3
from loguru import logger
from datetime import datetime, timedelta
import os
import hashlib
from queue import Queue, Empty
import threading
import weakref

DB_NAME = "database/pos.db"
POOL_SIZE = 20  # Increased for better concurrency


class ConnectionPool:
    """Simple connection pool for SQLite with automatic return on close."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._pool = Queue(maxsize=POOL_SIZE)
                cls._instance._size = POOL_SIZE
                cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        """Create initial connections."""
        for _ in range(self._size):
            conn = self._create_connection()
            self._pool.put(conn)

    def _create_connection(self):
        """Create a new database connection with WAL mode and foreign keys enabled."""
        try:
            conn = sqlite3.connect(DB_NAME, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.isolation_level = 'DEFERRED'
            logger.debug(f"New database connection created (pool)")
            return conn
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise

    def get_connection(self, timeout=5.0):
        """Get a connection from the pool. If pool empty, create a temporary connection."""
        try:
            conn = self._pool.get(timeout=timeout)
            # Rollback any pending transaction to ensure clean state
            try:
                conn.rollback()
            except:
                pass
            # Wrap the connection so that when close() is called, it returns to pool
            return _PooledConnection(conn, self)
        except Empty:
            logger.warning("Database connection pool exhausted – creating temporary unpooled connection")
            # Fallback: create a temporary connection (not pooled, but still works)
            return self._create_connection()

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if conn:
            try:
                conn.rollback()
                self._pool.put(conn)
            except Exception as e:
                logger.error(f"Failed to return connection to pool: {e}")
                try:
                    conn.close()
                except:
                    pass

    def close_all(self):
        """Close all connections in the pool (for app shutdown)."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass


class _PooledConnection:
    """Wrapper that returns the connection to the pool when closed."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._finalizer = weakref.finalize(self, self._close_and_return)

    def _close_and_return(self):
        if self._conn:
            self._pool.return_connection(self._conn)
            self._conn = None

    def close(self):
        self._close_and_return()
        self._finalizer.detach()

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        self.close()


_pool = ConnectionPool()


def connect_db():
    """
    Return a pooled connection (wrapped). The connection will automatically
    return to the pool when .close() is called or when garbage collected.
    """
    return _pool.get_connection()


def close_all_connections():
    """Close idle pooled database connections before replacing the database file."""
    _pool.close_all()


def release_connection(conn):
    """Explicitly return a connection to the pool (if not already closed)."""
    if hasattr(conn, 'close'):
        conn.close()


class DBContext:
    """Context manager for database connections. Usage: with DBContext() as conn:"""
    def __enter__(self):
        self.conn = connect_db()
        return self.conn
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()


def create_tables():
    """Create all necessary tables and indexes if they don't exist."""
    with DBContext() as conn:
        cursor = conn.cursor()
        logger.info("Creating/verifying database tables...")

        # ---------- Products ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            description TEXT,
            sold_by TEXT DEFAULT 'Each',
            price REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            sku TEXT,
            barcode TEXT,
            stock INTEGER DEFAULT 0,
            expire_date TEXT,
            low_stock INTEGER DEFAULT 0,
            image TEXT,
            supplier_id INTEGER,
            unit TEXT,
            warehouse TEXT,
            batch_no TEXT,
            manufacture_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(products)")
        cols = [c[1] for c in cursor.fetchall()]
        new_prod_cols = {
            'unit': 'TEXT', 'warehouse': 'TEXT', 'batch_no': 'TEXT',
            'manufacture_date': 'TEXT', 'last_updated': 'TIMESTAMP', 'supplier_id': 'INTEGER'
        }
        for col, dtype in new_prod_cols.items():
            if col not in cols:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {dtype}")
                logger.debug(f"Added column {col} to products table")

        # ---------- Sales ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT,
            total REAL,
            payment REAL,
            change_amount REAL,
            customer_id INTEGER,
            status TEXT DEFAULT 'completed',
            payment_type TEXT,
            discount_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cogs REAL DEFAULT 0,
            gross_profit REAL DEFAULT 0,
            net_profit REAL DEFAULT 0
        )
        """)
        cursor.execute("PRAGMA table_info(sales)")
        sales_cols = [c[1] for c in cursor.fetchall()]
        if 'customer_id' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN customer_id INTEGER")
            logger.debug("Added column customer_id to sales table")
        if 'status' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'completed'")
            logger.debug("Added column status to sales table")
        if 'payment_type' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN payment_type TEXT")
            logger.debug("Added column payment_type to sales table")
        if 'discount_amount' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN discount_amount REAL DEFAULT 0")
            logger.debug("Added column discount_amount to sales table")
        if 'cogs' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN cogs REAL DEFAULT 0")
            logger.debug("Added cogs column to sales table")
        if 'gross_profit' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN gross_profit REAL DEFAULT 0")
            logger.debug("Added gross_profit column to sales table")
        if 'net_profit' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN net_profit REAL DEFAULT 0")
            logger.debug("Added net_profit column to sales table")

        # ---------- Sale Items ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            product_name TEXT,
            qty INTEGER,
            price REAL,
            total REAL,
            cost REAL DEFAULT 0
        )
        """)
        cursor.execute("PRAGMA table_info(sale_items)")
        sale_items_cols = [c[1] for c in cursor.fetchall()]
        if 'cost' not in sale_items_cols:
            cursor.execute("ALTER TABLE sale_items ADD COLUMN cost REAL DEFAULT 0")
            logger.debug("Added cost column to sale_items table")

        # ---------- Categories ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)

        # ---------- Customers ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            address TEXT,
            total_visit INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0,
            points INTEGER DEFAULT 0,
            points_expiry_date TEXT,
            credit_limit REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            total_credit REAL DEFAULT 0,
            credit_balance REAL DEFAULT 0,
            remarks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(customers)")
        cust_cols = [c[1] for c in cursor.fetchall()]
        missing_cust_cols = {
            'points_expiry_date': 'TEXT',
            'credit_limit': 'REAL DEFAULT 0',
            'current_balance': 'REAL DEFAULT 0',
            'total_credit': 'REAL DEFAULT 0',
            'credit_balance': 'REAL DEFAULT 0',
            'remarks': 'TEXT'
        }
        for col, dtype in missing_cust_cols.items():
            if col not in cust_cols:
                cursor.execute(f"ALTER TABLE customers ADD COLUMN {col} {dtype}")
                logger.debug(f"Added column {col} to customers table")
        for col in ['total_visit', 'total_spent', 'points']:
            if col not in cust_cols:
                cursor.execute(f"ALTER TABLE customers ADD COLUMN {col} INTEGER DEFAULT 0")
                logger.debug(f"Added column {col} to customers table")

        # ---------- Payment Types ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS payment_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1
        )
        """)
        cursor.execute("SELECT COUNT(*) FROM payment_types")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("INSERT INTO payment_types (name) VALUES (?)", [("Cash",), ("Card",), ("Mobile Money",)])
            logger.info("Initialized default payment types")

        # ---------- Settings ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        default_settings = [
            ('tax_rate', '0'), ('tax_enabled', '0'),
            ('loyalty_points_per_dollar', '0'), ('loyalty_min_points_for_reward', '100'),
            ('loyalty_reward_discount', '5'), ('discount_enabled', '0'),
            ('discount_type', 'percentage'), ('discount_value', '0'),
            ('currency', 'Kyats (Ks)'),
            ('shop_name', 'ZAY POS'), ('shop_logo', ''),
            ('shop_phone', ''), ('shop_address', ''), ('shop_footer_message', ''),
            ('customer_display_youtube_url', ''),
            ('receipt_header', ''), ('receipt_footer', ''), ('show_customer_name', '1'),
            ('receipt_printer_name', ''), ('receipt_paper_size', '0'),
            ('receipt_print_quality', '203'), ('receipt_cash_drawer_use_receipt_printer', '1'),
            ('receipt_show_logo', '1'), ('receipt_show_shop_phone', '1'), ('receipt_show_shop_address', '1'),
            ('receipt_show_invoice', '1'), ('receipt_show_payment_type', '1'), ('receipt_show_customer', '1'),
            ('receipt_show_item_prices', '1'), ('receipt_show_subtotal', '1'), ('receipt_show_discount', '1'),
            ('receipt_show_tax', '1'), ('receipt_show_payment_change', '1'), ('receipt_show_thank_you', '1'),
            ('receipt_thank_you_text', 'THANK YOU'), ('receipt_line_width', '32'),
            ('language', 'en'), ('theme', 'Light'),
            ('points_expiry_months', '12'), ('points_dollar_value', '0.01'),
            ('window_resolution', '1366x768'),
            ('follow_system_theme', '1'),
            ('performance_low_end_mode', '1'),
            ('performance_product_page_size', '24'),
            ('performance_search_debounce_ms', '450'),
            ('performance_thumbnail_quality', 'low'),
            ('performance_customer_display_youtube_enabled', '0'),
            ('auto_backup_enabled', '0'), ('auto_backup_interval', '24'), ('auto_backup_max', '30')
        ]
        for key, val in default_settings:
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

        # ---------- Suppliers ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        cursor.execute("PRAGMA table_info(suppliers)")
        supp_cols = [c[1] for c in cursor.fetchall()]
        new_supp_cols = {
            'company_name': 'TEXT', 'tax_number': 'TEXT', 'website': 'TEXT',
            'payment_terms': 'TEXT', 'bank_account': 'TEXT', 'status': 'TEXT DEFAULT "Active"'
        }
        for col, dtype in new_supp_cols.items():
            if col not in supp_cols:
                cursor.execute(f"ALTER TABLE suppliers ADD COLUMN {col} {dtype}")
                logger.debug(f"Added column {col} to suppliers table")

        # ---------- Stock Movements ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            type TEXT,
            quantity INTEGER,
            old_stock INTEGER,
            new_stock INTEGER,
            reason TEXT,
            reference TEXT,
            created_by TEXT,
            notes TEXT,
            supplier_id INTEGER,
            location TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(stock_movements)")
        sm_cols = [c[1] for c in cursor.fetchall()]
        if 'notes' not in sm_cols:
            cursor.execute("ALTER TABLE stock_movements ADD COLUMN notes TEXT")
            logger.debug("Added column notes to stock_movements table")
        if 'supplier_id' not in sm_cols:
            cursor.execute("ALTER TABLE stock_movements ADD COLUMN supplier_id INTEGER")
            logger.debug("Added supplier_id column to stock_movements table")
        if 'location' not in sm_cols:
            cursor.execute("ALTER TABLE stock_movements ADD COLUMN location TEXT")
            logger.debug("Added location column to stock_movements table")

        # ---------- Purchase Orders ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_no TEXT UNIQUE,
            supplier_id INTEGER,
            order_date TEXT,
            total_amount REAL,
            status TEXT DEFAULT 'pending',
            discount REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Unpaid',
            received_by TEXT,
            invoice_attachment TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(purchase_orders)")
        po_cols = [c[1] for c in cursor.fetchall()]
        new_po_cols = {
            'discount': 'REAL', 'tax': 'REAL', 'payment_status': 'TEXT DEFAULT "Unpaid"',
            'received_by': 'TEXT', 'invoice_attachment': 'TEXT', 'notes': 'TEXT'
        }
        for col, dtype in new_po_cols.items():
            if col not in po_cols:
                cursor.execute(f"ALTER TABLE purchase_orders ADD COLUMN {col} {dtype}")
                logger.debug(f"Added column {col} to purchase_orders table")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            total REAL
        )
        """)

        # ---------- Supplier Payments ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            reference_no TEXT,
            payment_type TEXT DEFAULT 'Cash',
            notes TEXT,
            purchase_order_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id) ON DELETE SET NULL
        )
        """)
        logger.debug("Supplier payments table verified")

        # ---------- Expenses ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_no TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            expense_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            reference_no TEXT,
            notes TEXT,
            image TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(expenses)")
        expense_cols = [c[1] for c in cursor.fetchall()]
        if 'image' not in expense_cols:
            cursor.execute("ALTER TABLE expenses ADD COLUMN image TEXT")
            logger.debug("Added image column to expenses table")

        # ---------- Expense Categories ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.debug("Expense categories table verified")

        # Insert default expense categories
        cursor.execute("SELECT COUNT(*) FROM expense_categories")
        if cursor.fetchone()[0] == 0:
            default_categories = [
                ('Rent', 'Office/Shop rent'),
                ('Utilities', 'Electricity, Water, Internet'),
                ('Salaries', 'Employee salaries'),
                ('Marketing', 'Advertising, Promotion'),
                ('Maintenance', 'Equipment repair'),
                ('Transport', 'Delivery, Fuel'),
                ('Office Supplies', 'Stationery, Printing'),
                ('Taxes', 'Government taxes'),
                ('Other', 'Miscellaneous expenses')
            ]
            cursor.executemany("INSERT INTO expense_categories (name, description) VALUES (?, ?)", default_categories)
            logger.info("Default expense categories created")

        # ---------- Expense Budgets ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            budget_amount REAL NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, month, year)
        )
        """)
        logger.debug("Expense budgets table verified")

        # ---------- Expense Notification Settings ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_notification_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enable_notifications INTEGER DEFAULT 1,
            warning_threshold INTEGER DEFAULT 80,
            check_frequency TEXT DEFAULT 'daily',
            last_checked TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.debug("Expense notification settings table verified")

        cursor.execute("SELECT COUNT(*) FROM expense_notification_settings")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO expense_notification_settings (enable_notifications, warning_threshold, check_frequency)
                VALUES (1, 80, 'daily')
            """)
            logger.info("Default expense notification settings created")

        # ---------- Expense Alerts Log ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_alerts_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            month INTEGER,
            year INTEGER,
            budget_amount REAL,
            actual_amount REAL,
            used_percentage REAL,
            alert_type TEXT,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.debug("Expense alerts log table verified")

        # ---------- Expense Attachments ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            uploaded_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
        )
        """)
        logger.debug("Expense attachments table verified")

        # ---------- Credit Sales ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            total_amount REAL NOT NULL,
            paid_amount REAL DEFAULT 0,
            balance_amount REAL NOT NULL,
            sale_date TEXT NOT NULL,
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            sale_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            refunded_at TIMESTAMP,
            refund_reason TEXT,
            refund_type TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL
        )
        """)
        cursor.execute("PRAGMA table_info(credit_sales)")
        credit_sales_cols = [c[1] for c in cursor.fetchall()]
        if 'sale_id' not in credit_sales_cols:
            cursor.execute("ALTER TABLE credit_sales ADD COLUMN sale_id INTEGER")
            logger.debug("Added sale_id column to credit_sales table")
        for column, definition in (
            ('updated_at', 'TIMESTAMP'),
            ('refunded_at', 'TIMESTAMP'),
            ('refund_reason', 'TEXT'),
            ('refund_type', 'TEXT'),
        ):
            if column not in credit_sales_cols:
                cursor.execute(f"ALTER TABLE credit_sales ADD COLUMN {column} {definition}")
        logger.debug("Credit sales table verified")

        # Legacy payment ledger used by earlier credit-refund builds.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            customer_id INTEGER,
            payment_type TEXT NOT NULL,
            amount REAL NOT NULL,
            cash_drawer_id INTEGER,
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cash_drawer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            is_active INTEGER DEFAULT 0
        )
        """)

        # ---------- Credit Payments ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credit_sale_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            reference_no TEXT,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (credit_sale_id) REFERENCES credit_sales(id) ON DELETE CASCADE,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
        )
        """)
        logger.debug("Credit payments table verified")

        # ---------- Product Locations ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            quantity INTEGER DEFAULT 0,
            batch_no TEXT,
            expire_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(product_id, location)
        )
        """)
        logger.debug("Product locations table verified")

        # ---------- Users ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cashier',
            full_name TEXT,
            salt TEXT,
            force_password_change INTEGER DEFAULT 0,
            permissions TEXT,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [c[1] for c in cursor.fetchall()]
        if 'salt' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN salt TEXT")
            logger.debug("Added salt column to users table")
        if 'force_password_change' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
            logger.debug("Added force_password_change column to users table")
        if 'permissions' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT")
            logger.debug("Added permissions column to users table")
        if 'last_login' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
            logger.debug("Added last_login column to users table")
        if 'is_active' not in user_cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            logger.debug("Added is_active column to users table")

        # ---------- User Roles Table ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            permissions TEXT,
            is_system INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.debug("User roles table verified")

        # Create default roles
        cursor.execute("SELECT COUNT(*) FROM user_roles")
        if cursor.fetchone()[0] == 0:
            default_roles = [
                ('Admin', 'Full access to every page and action',
                 'dashboard,sales,create_sale,edit_sale,delete_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,delete_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,users,add_user,edit_user,delete_user,settings,edit_settings,backup,restore,factory_reset',
                 1),
                ('Manager', 'Manage daily operations without user deletion, restore, or factory reset',
                 'dashboard,sales,create_sale,edit_sale,refund_sale,sales_summary,products,add_product,edit_product,delete_product,ai_pages,inventory,stock_in,stock_out,adjustment,receipts,print_receipt,refund_receipt,customers,add_customer,edit_customer,expense,add_expense,edit_expense,delete_expense,manage_expense_categories,reports,credit,credit_sale,payment_collection,settings,backup',
                 0),
                ('Cashier', 'Process sales, print receipts, refund receipts, and manage sale customers',
                 'sales,create_sale,receipts,print_receipt,refund_receipt,customers,add_customer,credit,credit_sale,payment_collection',
                 0),
                ('Viewer', 'Read-only access to dashboards, lists, receipts, reports, and credit',
                 'dashboard,sales_summary,products,inventory,receipts,customers,reports,credit',
                 0),
            ]
            for name, desc, perms, is_system in default_roles:
                cursor.execute("""
                    INSERT INTO user_roles (name, description, permissions, is_system)
                    VALUES (?, ?, ?, ?)
                """, (name, desc, perms, is_system))
            logger.info("Default user roles created")

        # ---------- Fix Existing Admin User Role ----------
        cursor.execute("SELECT id, username, role FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()
        if admin:
            if admin[2] != 'Admin':
                cursor.execute("UPDATE users SET role = 'Admin' WHERE username = 'admin'")
                logger.info("Fixed admin user role from 'admin' to 'Admin'")

        # Insert default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            salt_bytes = os.urandom(32)
            salt_hex = salt_bytes.hex()
            password_hash = hashlib.pbkdf2_hmac('sha256', 'admin'.encode(), salt_bytes, 100000).hex()
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, full_name, salt, force_password_change, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ("admin", password_hash, "Admin", "Administrator", salt_hex, 0, 1))
            logger.info("Default admin user created with role 'Admin'")

        # ---------- Customer Points Log ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_points_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            points INTEGER NOT NULL,
            type TEXT NOT NULL,
            reference TEXT,
            expiry_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        )
        """)
        logger.debug("Customer points log table verified")

        # ---------- User Activity Log ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """)
        logger.debug("User activity log table verified")

        # ---------- Default category ----------
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO categories (name) VALUES ('General')")
            logger.info("Default category 'General' created")

        # ---------- Indexes ----------
        logger.debug("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice_no ON sales(invoice_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_points_log_customer ON customer_points_log(customer_id, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity_log(user_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity_log(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id, payment_date DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_categories_name ON expense_categories(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_credit_sales_customer ON credit_sales(customer_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_credit_payments_customer ON credit_payments(customer_id, payment_date DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_locations_product ON product_locations(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_locations_location ON product_locations(location)")

        # ---------- Add default cost and stock values for existing products ----------
        cursor.execute("UPDATE products SET cost = 0 WHERE cost IS NULL")
        cursor.execute("UPDATE products SET stock = 0 WHERE stock IS NULL")
        cursor.execute("UPDATE products SET low_stock = 0 WHERE low_stock IS NULL")
        
        conn.commit()
        logger.info("Database tables and indexes verified/created successfully")
        
        # ---------- Run Migrations ----------
        from models.migrations import run_migrations, fix_missing_columns
        try:
            run_migrations()
            fix_missing_columns()
        except Exception as e:
            logger.error(f"Migration failed: {e}")


# =============================================================================
# ✅ FIXED: expire_old_points() - Uses expiry_date
# =============================================================================
def expire_old_points():
    """
    Expire loyalty points based on expiry_date.
    
    ✅ FIX: Now correctly uses expiry_date column instead of created_at.
    Previously it only checked expiry_date IS NULL, which meant points with
    expiry_date set would never expire.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get expiry months from settings
        cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
        row = cursor.fetchone()
        expiry_months = int(row[0]) if row else 12
        
        if expiry_months <= 0:
            # If expiry is disabled (0 = never), skip expiration
            logger.info("Points expiry is disabled (expiry_months = 0)")
            return 0
        
        cutoff = (datetime.now() - timedelta(days=expiry_months * 30)).strftime("%Y-%m-%d")
        
        # ✅ FIX: Primary expiration based on expiry_date
        cursor.execute("""
            SELECT customer_id, SUM(points) as expired_points
            FROM customer_points_log
            WHERE type = 'earn'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) < date('now')
            GROUP BY customer_id
            HAVING expired_points > 0
        """)
        expired = cursor.fetchall()
        
        # ✅ Also handle old data where expiry_date is NULL (fallback to created_at)
        cursor.execute("""
            SELECT customer_id, SUM(points) as expired_points
            FROM customer_points_log
            WHERE type = 'earn'
              AND expiry_date IS NULL
              AND date(created_at) < ?
            GROUP BY customer_id
            HAVING expired_points > 0
        """, (cutoff,))
        old_expired = cursor.fetchall()
        
        # Combine both results
        all_expired = expired + old_expired
        
        affected = 0
        for cust_id, pts in all_expired:
            # Deduct points from customer
            cursor.execute("UPDATE customers SET points = points - ? WHERE id = ?", (pts, cust_id))
            
            # Log the expiration
            cursor.execute("""
                INSERT INTO customer_points_log (customer_id, points, type, reference, created_at)
                VALUES (?, ?, 'expire', ?, ?)
            """, (cust_id, pts, f"auto_expiry_{today}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            
            # Update expiry_date on original entries to prevent double expiration
            cursor.execute("""
                UPDATE customer_points_log
                SET expiry_date = ?
                WHERE customer_id = ? 
                  AND type = 'earn' 
                  AND (expiry_date IS NULL OR expiry_date != '')
                  AND (date(expiry_date) < date('now') OR date(created_at) < ?)
            """, (today, cust_id, cutoff))
            
            affected += 1
        
        conn.commit()
        if affected:
            logger.info(f"Expired loyalty points for {affected} customer(s)")
        return affected


# =============================================================================
# ✅ FIXED: expire_points_for_customer() - Uses expiry_date
# =============================================================================
def expire_points_for_customer(customer_id):
    """
    Expire loyalty points for a specific customer based on expiry_date.
    
    ✅ FIX: Now correctly uses expiry_date column instead of created_at.
    """
    with DBContext() as conn:
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get expiry months from settings
        cursor.execute("SELECT value FROM settings WHERE key='points_expiry_months'")
        row = cursor.fetchone()
        expiry_months = int(row[0]) if row else 12
        
        if expiry_months <= 0:
            # If expiry is disabled (0 = never), skip expiration
            return 0
        
        cutoff = (datetime.now() - timedelta(days=expiry_months * 30)).strftime("%Y-%m-%d")
        
        # ✅ FIX: Primary expiration based on expiry_date
        cursor.execute("""
            SELECT SUM(points) as expired_points
            FROM customer_points_log
            WHERE customer_id = ?
              AND type = 'earn'
              AND expiry_date IS NOT NULL
              AND date(expiry_date) < date('now')
            GROUP BY customer_id
        """, (customer_id,))
        row = cursor.fetchone()
        
        # Also check old data where expiry_date is NULL (fallback to created_at)
        cursor.execute("""
            SELECT SUM(points) as expired_points
            FROM customer_points_log
            WHERE customer_id = ?
              AND type = 'earn'
              AND expiry_date IS NULL
              AND date(created_at) < ?
            GROUP BY customer_id
        """, (customer_id, cutoff))
        old_row = cursor.fetchone()
        
        pts = 0
        if row and row[0]:
            pts += row[0]
        if old_row and old_row[0]:
            pts += old_row[0]
        
        if pts == 0:
            return 0
        
        # Deduct points
        cursor.execute("UPDATE customers SET points = points - ? WHERE id = ?", (pts, customer_id))
        
        # Log the expiration
        cursor.execute("""
            INSERT INTO customer_points_log (customer_id, points, type, reference, created_at)
            VALUES (?, ?, 'expire', ?, ?)
        """, (customer_id, pts, f"auto_expiry_{today}", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        # Update expiry_date on original entries to prevent double expiration
        cursor.execute("""
            UPDATE customer_points_log
            SET expiry_date = ?
            WHERE customer_id = ? 
              AND type = 'earn' 
              AND (expiry_date IS NULL OR expiry_date != '')
              AND (date(expiry_date) < date('now') OR date(created_at) < ?)
        """, (today, customer_id, cutoff))
        
        conn.commit()
        return pts


def check_and_recover(show_gui=True):
    with DBContext() as conn:
        cursor = conn.cursor()
        issues = []
        cursor.execute("""
            SELECT s.id, s.invoice_no, s.created_at
            FROM sales s
            WHERE s.status NOT IN ('completed', 'refunded')
              AND NOT EXISTS (SELECT 1 FROM sale_items WHERE sale_id = s.id)
        """)
        orphan = cursor.fetchall()
        if orphan:
            issues.append(('orphan_sales', orphan))
        cursor.execute("""
            SELECT id, invoice_no, created_at
            FROM sales
            WHERE status NOT IN ('completed', 'refunded')
              AND julianday('now') - julianday(created_at) > 1.0/24
        """)
        stale = cursor.fetchall()
        if stale:
            issues.append(('stale_sales', stale))
        cursor.execute("SELECT id, name, stock FROM products WHERE stock < 0")
        neg_stock = cursor.fetchall()
        if neg_stock:
            issues.append(('neg_stock', neg_stock))
        cursor.execute("SELECT id, name, points FROM customers WHERE points < 0")
        neg_points = cursor.fetchall()
        if neg_points:
            issues.append(('neg_points', neg_points))
    if not issues:
        return False
    if not show_gui:
        logger.warning(f"Recovery found issues: {issues}")
        return False
    from PyQt6.QtWidgets import QMessageBox
    msg = "Database recovery found inconsistencies:\n\n"
    for cat, data in issues:
        if cat == 'orphan_sales':
            msg += f"• {len(data)} sale(s) with no items\n"
        elif cat == 'stale_sales':
            msg += f"• {len(data)} stale sale(s)\n"
        elif cat == 'neg_stock':
            msg += f"• {len(data)} product(s) with negative stock\n"
        elif cat == 'neg_points':
            msg += f"• {len(data)} customer(s) with negative points\n"
    msg += "\nRepair automatically?"
    reply = QMessageBox.question(None, "Database Recovery", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    if reply != QMessageBox.StandardButton.Yes:
        return False
    with DBContext() as conn:
        cursor = conn.cursor()
        try:
            for cat, data in issues:
                if cat in ('orphan_sales', 'stale_sales'):
                    for sid, inv, _ in data:
                        cursor.execute("DELETE FROM sales WHERE id = ?", (sid,))
                        logger.info(f"Deleted {cat[:-7]} sale {inv}")
                elif cat == 'neg_stock':
                    for pid, name, _ in data:
                        cursor.execute("UPDATE products SET stock = 0 WHERE id = ?", (pid,))
                        logger.info(f"Reset negative stock for {name}")
                elif cat == 'neg_points':
                    for cid, name, _ in data:
                        cursor.execute("UPDATE customers SET points = 0 WHERE id = ?", (cid,))
                        logger.info(f"Reset negative points for {name}")
            conn.commit()
            QMessageBox.information(None, "Recovery Complete", "Database repaired.")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Recovery failed: {e}")
            QMessageBox.critical(None, "Recovery Error", f"Could not repair: {e}")
            return False
