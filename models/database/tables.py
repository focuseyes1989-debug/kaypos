# models/database/tables.py
"""
Database table creation and schema management.
"""

import os
import hashlib
import re
from loguru import logger
from datetime import datetime, timedelta
from models.database.connection import DBContext

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
        cursor.execute("PRAGMA table_info(products)")
        cols = [c[1] for c in cursor.fetchall()]
        new_prod_cols = {
            'unit': 'TEXT', 'warehouse': 'TEXT', 'batch_no': 'TEXT',
            'manufacture_date': 'TEXT', 'last_updated': 'TIMESTAMP', 
            'supplier_id': 'INTEGER', 'is_favourite': 'INTEGER DEFAULT 0',
            'category_id': 'INTEGER', 'base_unit': "TEXT DEFAULT 'pcs'",
            'pack_unit': "TEXT DEFAULT ''", 'pack_size': 'INTEGER DEFAULT 1',
            'restaurant_modifiers': 'TEXT'
        }
        for col, dtype in new_prod_cols.items():
            if col not in cols:
                try:
                    cursor.execute(f"ALTER TABLE products ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added column {col} to products table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

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
        missing_sales_cols = ['customer_id', 'status', 'payment_type', 'discount_amount', 
                             'cogs', 'gross_profit', 'net_profit']
        for col in missing_sales_cols:
            if col not in sales_cols:
                try:
                    if col == 'customer_id':
                        cursor.execute("ALTER TABLE sales ADD COLUMN customer_id INTEGER")
                    elif col == 'status':
                        cursor.execute("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'completed'")
                    elif col == 'payment_type':
                        cursor.execute("ALTER TABLE sales ADD COLUMN payment_type TEXT")
                    elif col == 'discount_amount':
                        cursor.execute("ALTER TABLE sales ADD COLUMN discount_amount REAL DEFAULT 0")
                    elif col == 'cogs':
                        cursor.execute("ALTER TABLE sales ADD COLUMN cogs REAL DEFAULT 0")
                    elif col == 'gross_profit':
                        cursor.execute("ALTER TABLE sales ADD COLUMN gross_profit REAL DEFAULT 0")
                    elif col == 'net_profit':
                        cursor.execute("ALTER TABLE sales ADD COLUMN net_profit REAL DEFAULT 0")
                    logger.debug(f"Added column {col} to sales table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

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
            try:
                cursor.execute("ALTER TABLE sale_items ADD COLUMN cost REAL DEFAULT 0")
                logger.debug("Added cost column to sale_items table")
            except Exception as e:
                logger.warning(f"Could not add cost column: {e}")
        if 'variant_id' not in sale_items_cols:
            try:
                cursor.execute("ALTER TABLE sale_items ADD COLUMN variant_id INTEGER")
                logger.debug("Added variant_id column to sale_items table")
            except Exception as e:
                logger.warning(f"Could not add variant_id column: {e}")
        for col, dtype in {
            'product_id': 'INTEGER',
            'location_id': 'INTEGER',
            'location': 'TEXT',
            'batch_no': 'TEXT',
            'expire_date': 'TEXT',
            'wholesale_regular_price': 'REAL DEFAULT 0',
            'wholesale_savings': 'REAL DEFAULT 0',
            'wholesale_tier_min_qty': 'INTEGER',
            'wholesale_unit_label': 'TEXT',
        }.items():
            if col not in sale_items_cols:
                try:
                    cursor.execute(f"ALTER TABLE sale_items ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added {col} column to sale_items table")
                except Exception as e:
                    logger.warning(f"Could not add {col} column: {e}")

        # ---------- Product Variants ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            size TEXT,
            color TEXT,
            sku TEXT,
            barcode TEXT,
            price REAL DEFAULT 0,
            cost REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            low_stock INTEGER DEFAULT 0,
            image TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_product ON product_variants(product_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_barcode ON product_variants(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_variants_sku ON product_variants(sku)")

        # ---------- Wholesale Price Tiers ----------
        from utils.wholesale_pricing import ensure_wholesale_schema
        ensure_wholesale_schema(cursor)

        # ---------- Categories (Enhanced - with all columns) ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT,
            description TEXT,
            parent_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            color TEXT DEFAULT '#6c5ce7',
            icon TEXT DEFAULT '📁',
            image_path TEXT,
            status TEXT DEFAULT 'active',
            code TEXT,
            notes TEXT,
            is_system INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0,
            group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
        )
        """)
        
        # Create unique index for slug (instead of UNIQUE constraint)
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_slug_unique ON categories(slug)")
            logger.debug("Created unique index for slug column")
        except Exception as e:
            logger.warning(f"Could not create unique index for slug: {e}")
        
        # Check and add missing columns
        cursor.execute("PRAGMA table_info(categories)")
        existing_cols = [c[1] for c in cursor.fetchall()]
        
        columns_to_add = {
            'parent_id': 'INTEGER',
            'sort_order': 'INTEGER DEFAULT 0',
            'color': 'TEXT DEFAULT "#6c5ce7"',
            'icon': 'TEXT DEFAULT "📁"',
            'image_path': 'TEXT',
            'status': 'TEXT DEFAULT "active"',
            'code': 'TEXT',
            'notes': 'TEXT',
            'is_system': 'INTEGER DEFAULT 0',
            'is_favorite': 'INTEGER DEFAULT 0',
            'group_id': 'INTEGER',
            'updated_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        for col, dtype in columns_to_add.items():
            if col not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE categories ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added column {col} to categories table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

        # Update slugs for existing categories
        try:
            cursor.execute("SELECT id, name FROM categories WHERE slug IS NULL OR slug = ''")
            rows = cursor.fetchall()
            if rows:
                logger.info(f"Updating slugs for {len(rows)} categories...")
                for cat_id, name in rows:
                    slug = name.lower().strip()
                    slug = slug.replace(' ', '-')
                    slug = slug.replace('(', '')
                    slug = slug.replace(')', '')
                    slug = slug.replace('/', '-')
                    slug = slug.replace('&', 'and')
                    slug = slug.replace("'", '')
                    slug = slug.replace('"', '')
                    slug = re.sub(r'-+', '-', slug)
                    
                    if not slug:
                        slug = f"category-{cat_id}"
                    
                    cursor.execute("SELECT id FROM categories WHERE slug = ? AND id != ?", (slug, cat_id))
                    if cursor.fetchone():
                        slug = f"{slug}-{cat_id}"
                    
                    cursor.execute("UPDATE categories SET slug = ? WHERE id = ?", (slug, cat_id))
                conn.commit()
                logger.info(f"Updated slugs for {len(rows)} categories")
        except Exception as e:
            logger.warning(f"Could not update slugs: {e}")

        # ---------- Category Groups ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            icon TEXT,
            color TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            is_favorite INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ---------- Category Stats ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_stats (
            category_id INTEGER PRIMARY KEY,
            product_count INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        )
        """)

        # Populate category_stats for existing categories
        try:
            cursor.execute("SELECT id, name FROM categories")
            categories = cursor.fetchall()
            if categories:
                logger.info(f"Initializing category_stats for {len(categories)} categories...")
                for (cat_id, name) in categories:
                    cursor.execute("""
                        SELECT COUNT(*) FROM products 
                        WHERE category_id = ? AND (sold_by IS NULL OR sold_by != 'Service')
                    """, (cat_id,))
                    product_count = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        INSERT OR IGNORE INTO category_stats (category_id, product_count)
                        VALUES (?, ?)
                    """, (cat_id, product_count))
                conn.commit()
                logger.info(f"Initialized category_stats for {len(categories)} categories")
        except Exception as e:
            logger.warning(f"Could not populate category_stats: {e}")

        # ---------- Category Activity Log ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS category_activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            user_id INTEGER,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
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
                try:
                    cursor.execute(f"ALTER TABLE customers ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added column {col} to customers table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")
        for col in ['total_visit', 'total_spent', 'points']:
            if col not in cust_cols:
                try:
                    cursor.execute(f"ALTER TABLE customers ADD COLUMN {col} INTEGER DEFAULT 0")
                    logger.debug(f"Added column {col} to customers table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

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
            ('performance_product_page_size', '25'),
            ('performance_search_debounce_ms', '450'),
            ('performance_thumbnail_quality', 'low'),
            ('performance_customer_display_youtube_enabled', '0'),
            ('auto_backup_enabled', '0'), ('auto_backup_interval', '24'), ('auto_backup_max', '30'),
            ('credit_due_days', '15'), ('credit_limit_enabled', 'true')
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
                try:
                    cursor.execute(f"ALTER TABLE suppliers ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added column {col} to suppliers table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

        # ---------- Stock Movements (FIXED - Added customer_id) ----------
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
            customer_id INTEGER,  -- ✅ Added
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Check and add missing columns
        cursor.execute("PRAGMA table_info(stock_movements)")
        sm_cols = [c[1] for c in cursor.fetchall()]
        
        if 'notes' not in sm_cols:
            try:
                cursor.execute("ALTER TABLE stock_movements ADD COLUMN notes TEXT")
                logger.debug("Added column notes to stock_movements table")
            except Exception as e:
                logger.warning(f"Could not add notes column: {e}")
                
        if 'supplier_id' not in sm_cols:
            try:
                cursor.execute("ALTER TABLE stock_movements ADD COLUMN supplier_id INTEGER")
                logger.debug("Added supplier_id column to stock_movements table")
            except Exception as e:
                logger.warning(f"Could not add supplier_id column: {e}")
                
        if 'location' not in sm_cols:
            try:
                cursor.execute("ALTER TABLE stock_movements ADD COLUMN location TEXT")
                logger.debug("Added location column to stock_movements table")
            except Exception as e:
                logger.warning(f"Could not add location column: {e}")
        
        # ✅ Add customer_id column if not exists
        if 'customer_id' not in sm_cols:
            try:
                cursor.execute("ALTER TABLE stock_movements ADD COLUMN customer_id INTEGER")
                logger.debug("Added customer_id column to stock_movements table")
            except Exception as e:
                logger.warning(f"Could not add customer_id column: {e}")

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
                try:
                    cursor.execute(f"ALTER TABLE purchase_orders ADD COLUMN {col} {dtype}")
                    logger.debug(f"Added column {col} to purchase_orders table")
                except Exception as e:
                    logger.warning(f"Could not add column {col}: {e}")

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
            try:
                cursor.execute("ALTER TABLE expenses ADD COLUMN image TEXT")
                logger.debug("Added image column to expenses table")
            except Exception as e:
                logger.warning(f"Could not add image column: {e}")

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
            try:
                cursor.execute("ALTER TABLE credit_sales ADD COLUMN sale_id INTEGER")
                logger.debug("Added sale_id column to credit_sales table")
            except Exception as e:
                logger.warning(f"Could not add sale_id column: {e}")
        # Refund metadata was added after the original credit-sales table.
        # Keep this repair here so restored/older databases work on startup.
        for column, definition in (
            ('updated_at', 'TIMESTAMP'),
            ('refunded_at', 'TIMESTAMP'),
            ('refund_reason', 'TEXT'),
            ('refund_type', 'TEXT'),
        ):
            if column not in credit_sales_cols:
                cursor.execute(f"ALTER TABLE credit_sales ADD COLUMN {column} {definition}")

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

        # Credit Adjustments / Audit Trail Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            credit_sale_id INTEGER,
            amount REAL NOT NULL,
            adjustment_type TEXT NOT NULL,
            reason TEXT,
            reference_no TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
            FOREIGN KEY (credit_sale_id) REFERENCES credit_sales(id) ON DELETE SET NULL
        )
        """)
        logger.info("Created credit_adjustments table")

        # Credit Transactions (Unified Audit Trail)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credit_sale_id INTEGER,
            customer_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL DEFAULT 'legacy',
            reference_no TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            -- Backward-compatible aliases used by earlier packaged builds.
            type TEXT,
            description TEXT,
            payment_id INTEGER,
            FOREIGN KEY (credit_sale_id) REFERENCES credit_sales(id) ON DELETE SET NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
        )
        """)
        cursor.execute("PRAGMA table_info(credit_transactions)")
        credit_transaction_cols = [c[1] for c in cursor.fetchall()]
        for column, definition in (
            ('type', 'TEXT'),
            ('description', 'TEXT'),
            ('payment_id', 'INTEGER'),
        ):
            if column not in credit_transaction_cols:
                cursor.execute(f"ALTER TABLE credit_transactions ADD COLUMN {column} {definition}")
        logger.info("Created credit_transactions table")

        # ---------- Product Locations (BATCH-AWARE) ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            location TEXT NOT NULL,
            batch_no TEXT,
            expire_date TEXT,
            quantity INTEGER DEFAULT 0,
            expiry_discount_enabled INTEGER DEFAULT 0,
            expiry_discount_percent REAL DEFAULT 0,
            expiry_discount_start_date TEXT,
            expiry_discount_end_date TEXT,
            clearance_note TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            UNIQUE(product_id, location, batch_no, expire_date)
        )
        """)
        cursor.execute("PRAGMA table_info(product_locations)")
        pl_cols = [c[1] for c in cursor.fetchall()]
        for column, definition in {
            'expiry_discount_enabled': 'INTEGER DEFAULT 0',
            'expiry_discount_percent': 'REAL DEFAULT 0',
            'expiry_discount_start_date': 'TEXT',
            'expiry_discount_end_date': 'TEXT',
            'clearance_note': 'TEXT',
        }.items():
            if column not in pl_cols:
                cursor.execute(f"ALTER TABLE product_locations ADD COLUMN {column} {definition}")
        
        # FIFO-friendly indexes
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pl_fifo 
        ON product_locations(product_id, expire_date ASC, last_updated ASC)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pl_product 
        ON product_locations(product_id)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pl_location 
        ON product_locations(location)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pl_expiry 
        ON product_locations(expire_date)
        """)

        # ---------- Locations ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        INSERT OR IGNORE INTO locations (name)
        SELECT DISTINCT location FROM product_locations 
        WHERE location IS NOT NULL AND location != ''
        """)
        cursor.execute("""
        INSERT OR IGNORE INTO locations (name)
        SELECT DISTINCT warehouse FROM products 
        WHERE warehouse IS NOT NULL AND warehouse != ''
        """)

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
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN salt TEXT")
                logger.debug("Added salt column to users table")
            except Exception as e:
                logger.warning(f"Could not add salt column: {e}")
        if 'force_password_change' not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN force_password_change INTEGER DEFAULT 0")
                logger.debug("Added force_password_change column to users table")
            except Exception as e:
                logger.warning(f"Could not add force_password_change column: {e}")
        if 'permissions' not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN permissions TEXT")
                logger.debug("Added permissions column to users table")
            except Exception as e:
                logger.warning(f"Could not add permissions column: {e}")
        if 'last_login' not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login TIMESTAMP")
                logger.debug("Added last_login column to users table")
            except Exception as e:
                logger.warning(f"Could not add last_login column: {e}")
        if 'is_active' not in user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
                logger.debug("Added is_active column to users table")
            except Exception as e:
                logger.warning(f"Could not add is_active column: {e}")

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

        # ---------- Default category ----------
        cursor.execute("SELECT COUNT(*) FROM categories")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO categories (name, slug) VALUES ('General', 'general')")
            logger.info("Default category 'General' created")

        # ---------- CREDIT INDEXES ----------
        logger.debug("Creating credit indexes...")
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_status 
        ON credit_sales(customer_id, status)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_sales_status_date 
        ON credit_sales(status, due_date)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_balance_due
        ON credit_sales(customer_id, balance_amount, due_date)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_payments_customer_date
        ON credit_payments(customer_id, payment_date DESC)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_adjustments_customer
        ON credit_adjustments(customer_id, created_at DESC)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_transactions_customer
        ON credit_transactions(customer_id, created_at DESC)
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_credit_transactions_type
        ON credit_transactions(transaction_type)
        """)

        # ---------- Held Sales ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS held_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hold_no TEXT UNIQUE,
            cart_json TEXT NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            payment_type TEXT,
            note TEXT,
            total_amount REAL DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        logger.debug("Held sales table verified")

        # ---------- Restaurant Mode ----------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            table_id INTEGER,
            order_type TEXT DEFAULT 'Dine-in',
            status TEXT DEFAULT 'open',
            kitchen_status TEXT DEFAULT 'draft',
            cart_json TEXT NOT NULL,
            customer_id INTEGER,
            customer_name TEXT,
            note TEXT,
            total_amount REAL DEFAULT 0,
            item_count INTEGER DEFAULT 0,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_to_kitchen_at TIMESTAMP,
            settled_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            sale_id INTEGER,
            invoice_no TEXT,
            settled_total REAL DEFAULT 0,
            payment_amount REAL DEFAULT 0,
            change_amount REAL DEFAULT 0,
            payment_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (table_id) REFERENCES restaurant_tables(id) ON DELETE SET NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            unit_price REAL DEFAULT 0,
            base_price REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            note TEXT,
            line_id TEXT,
            status TEXT DEFAULT 'active',
            kitchen_status TEXT DEFAULT 'draft',
            sent_quantity REAL DEFAULT 0,
            cancelled_quantity REAL DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES restaurant_orders(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_order_modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_item_id INTEGER NOT NULL,
            group_name TEXT,
            modifier_name TEXT NOT NULL,
            modifier_type TEXT DEFAULT 'note',
            price_delta REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_item_id) REFERENCES restaurant_order_items(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no TEXT UNIQUE NOT NULL,
            order_id INTEGER NOT NULL,
            status TEXT DEFAULT 'sent',
            ticket_signature TEXT NOT NULL,
            printed INTEGER DEFAULT 0,
            note TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES restaurant_orders(id) ON DELETE CASCADE
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS restaurant_kitchen_ticket_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER NOT NULL,
            order_item_id INTEGER,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            modifier_summary TEXT,
            quantity REAL DEFAULT 0,
            note TEXT,
            status TEXT DEFAULT 'sent',
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            preparing_at TIMESTAMP,
            ready_at TIMESTAMP,
            served_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES restaurant_kitchen_tickets(id) ON DELETE CASCADE,
            FOREIGN KEY (order_item_id) REFERENCES restaurant_order_items(id) ON DELETE SET NULL
        )
        """)
        logger.debug("Restaurant mode tables verified")

        # ---------- Category Indexes ----------
        logger.debug("Creating category indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_status ON categories(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_sort ON categories(sort_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_favorite ON categories(is_favorite)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_group ON categories(group_id)")

        # ---------- Other Indexes ----------
        logger.debug("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice_no ON sales(invoice_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_held_sales_created_at ON held_sales(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_table ON restaurant_orders(table_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_status ON restaurant_orders(status, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_orders_type_status ON restaurant_orders(order_type, status, updated_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_order ON restaurant_order_items(order_id, sort_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_items_status ON restaurant_order_items(order_id, status, kitchen_status)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_order_items_line ON restaurant_order_items(order_id, line_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_order_modifiers_item ON restaurant_order_modifiers(order_item_id)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_signature ON restaurant_kitchen_tickets(order_id, ticket_signature)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_tickets_status ON restaurant_kitchen_tickets(status, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_ticket ON restaurant_kitchen_ticket_items(ticket_id, sort_order)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_restaurant_kitchen_ticket_items_status ON restaurant_kitchen_ticket_items(ticket_id, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_favourite ON products(is_favourite)")
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

        # ---------- Add default cost and stock values ----------
        cursor.execute("UPDATE products SET cost = 0 WHERE cost IS NULL")
        cursor.execute("UPDATE products SET stock = 0 WHERE stock IS NULL")
        cursor.execute("UPDATE products SET low_stock = 0 WHERE low_stock IS NULL")
        
        conn.commit()
        logger.info("Database tables and indexes verified/created successfully")
        
        # ---------- Run Migrations ----------
        from models.database.migrations import run_migrations, fix_missing_columns
        try:
            run_migrations()
            fix_missing_columns()
        except Exception as e:
            logger.error(f"Migration failed: {e}")


def ensure_schema():
    """Ensure database schema exists and is up to date."""
    create_tables()
