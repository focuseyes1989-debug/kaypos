# models/database/migrations_data.py
"""
Migration definitions with rollback support.
"""

from models.database.migration_manager import Migration

MIGRATIONS = [
    # =========================================================================
    # INITIAL MIGRATIONS
    # =========================================================================
    Migration(
        version="1.0.0",
        name="Initial Schema",
        description="Create all initial tables (handled by create_tables)",
        up_sql="",
        down_sql=""
    ),
    
    Migration(
        version="1.1.0",
        name="Add Credit Limit to Customers",
        description="Add credit_limit, current_balance, and remarks columns to customers table",
        up_sql="",
        down_sql=""
    ),
    
    Migration(
        version="1.2.0",
        name="Add Business Info to Settings",
        description="Add shop_phone, shop_address, shop_footer_message to settings",
        up_sql="""
            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_phone', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_address', '');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('shop_footer_message', '');
        """,
        down_sql="""
            DELETE FROM settings WHERE key IN ('shop_phone', 'shop_address', 'shop_footer_message');
        """
    ),
    
    Migration(
        version="1.3.0",
        name="Add User Roles Table",
        description="Create user_roles table and insert default roles",
        up_sql="""
            CREATE TABLE IF NOT EXISTS user_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                permissions TEXT,
                is_system INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT OR IGNORE INTO user_roles (name, description, permissions, is_system) VALUES 
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
             0);
        """,
        down_sql="""
            DROP TABLE IF EXISTS user_roles;
        """
    ),
    
    Migration(
        version="1.4.0",
        name="Add User Activity Log",
        description="Create user_activity_log table",
        up_sql="""
            CREATE TABLE IF NOT EXISTS user_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_activity_user ON user_activity_log(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity_log(action);
        """,
        down_sql="""
            DROP TABLE IF EXISTS user_activity_log;
        """,
        dependencies=["1.3.0"]
    ),
    
    Migration(
        version="1.5.0",
        name="Add COGS Columns to Sales",
        description="Add cogs, gross_profit, net_profit to sales table",
        up_sql="",
        down_sql=""
    ),
    
    Migration(
        version="1.6.0",
        name="Add Auto Backup Settings",
        description="Add auto backup settings to settings table",
        up_sql="""
            INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_backup_enabled', '0');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_backup_interval', '24');
            INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_backup_max', '30');
        """,
        down_sql="""
            DELETE FROM settings WHERE key IN ('auto_backup_enabled', 'auto_backup_interval', 'auto_backup_max');
        """
    ),
    
    Migration(
        version="1.7.0",
        name="Add Product Locations Table",
        description="Support multiple locations per product",
        up_sql="""
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
            );
            
            INSERT INTO product_locations (product_id, location, quantity)
            SELECT id, warehouse, stock 
            FROM products 
            WHERE warehouse IS NOT NULL AND warehouse != '' AND stock > 0;
            
            CREATE INDEX IF NOT EXISTS idx_product_locations_product ON product_locations(product_id);
            CREATE INDEX IF NOT EXISTS idx_product_locations_location ON product_locations(location);
        """,
        down_sql="""
            DROP TABLE IF EXISTS product_locations;
        """
    ),
    
    Migration(
        version="1.8.0",
        name="Add Location Column to Stock Movements",
        description="Add location column to stock_movements table",
        up_sql="",
        down_sql=""
    ),
    
    Migration(
        version="1.9.0",
        name="Add Locations Table",
        description="Create locations table for better location management",
        up_sql="""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT OR IGNORE INTO locations (name)
            SELECT DISTINCT location FROM product_locations 
            WHERE location IS NOT NULL AND location != '';
            
            INSERT OR IGNORE INTO locations (name)
            SELECT DISTINCT warehouse FROM products 
            WHERE warehouse IS NOT NULL AND warehouse != '';
            
            CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(name);
        """,
        down_sql="""
            DROP TABLE IF EXISTS locations;
        """,
        dependencies=["1.7.0"]
    ),
    
    # =========================================================================
    # VERSION 2.0.0 - SUPPLIER PAYMENTS
    # =========================================================================
    Migration(
        version="2.0.0",
        name="Add Supplier Payments Table",
        description="Create supplier_payments table for tracking payments to suppliers",
        up_sql="""
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
            );
            
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id, payment_date DESC);
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_po ON supplier_payments(purchase_order_id);
        """,
        down_sql="""
            DROP TABLE IF EXISTS supplier_payments;
        """
    ),
    
    # =========================================================================
    # VERSION 2.1.0 - EXPENSE MANAGEMENT
    # =========================================================================
    Migration(
        version="2.1.0",
        name="Add Expense Management Tables",
        description="Create expense_categories, expense_budgets, expense_notification_settings, expense_alerts_log, expense_attachments tables",
        up_sql="""
            CREATE TABLE IF NOT EXISTS expense_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT OR IGNORE INTO expense_categories (name, description) VALUES 
            ('Rent', 'Office/Shop rent'),
            ('Utilities', 'Electricity, Water, Internet'),
            ('Salaries', 'Employee salaries'),
            ('Marketing', 'Advertising, Promotion'),
            ('Maintenance', 'Equipment repair'),
            ('Transport', 'Delivery, Fuel'),
            ('Office Supplies', 'Stationery, Printing'),
            ('Taxes', 'Government taxes'),
            ('Other', 'Miscellaneous expenses');
            
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
            );
            
            CREATE TABLE IF NOT EXISTS expense_notification_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enable_notifications INTEGER DEFAULT 1,
                warning_threshold INTEGER DEFAULT 80,
                check_frequency TEXT DEFAULT 'daily',
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT OR IGNORE INTO expense_notification_settings (enable_notifications, warning_threshold, check_frequency)
            VALUES (1, 80, 'daily');
            
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
            );
            
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
            );
            
            CREATE INDEX IF NOT EXISTS idx_expense_categories_name ON expense_categories(name);
            CREATE INDEX IF NOT EXISTS idx_expense_budgets_category ON expense_budgets(category, year, month);
            CREATE INDEX IF NOT EXISTS idx_expense_alerts_category ON expense_alerts_log(category, year, month);
            CREATE INDEX IF NOT EXISTS idx_expense_alerts_read ON expense_alerts_log(is_read);
        """,
        down_sql="""
            DROP TABLE IF EXISTS expense_attachments;
            DROP TABLE IF EXISTS expense_alerts_log;
            DROP TABLE IF EXISTS expense_notification_settings;
            DROP TABLE IF EXISTS expense_budgets;
            DROP TABLE IF EXISTS expense_categories;
        """
    ),
    
    # =========================================================================
    # VERSION 2.2.0 - CREDIT SALES
    # =========================================================================
    Migration(
        version="2.2.0",
        name="Add Credit Sales Tables",
        description="Create credit_sales and credit_payments tables",
        up_sql="""
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
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL
            );
            
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
            );
            
            CREATE INDEX IF NOT EXISTS idx_credit_sales_customer ON credit_sales(customer_id, status);
            CREATE INDEX IF NOT EXISTS idx_credit_sales_invoice ON credit_sales(invoice_no);
            CREATE INDEX IF NOT EXISTS idx_credit_sales_status ON credit_sales(status);
            CREATE INDEX IF NOT EXISTS idx_credit_payments_customer ON credit_payments(customer_id, payment_date DESC);
            CREATE INDEX IF NOT EXISTS idx_credit_payments_credit_sale ON credit_payments(credit_sale_id);
        """,
        down_sql="""
            DROP TABLE IF EXISTS credit_payments;
            DROP TABLE IF EXISTS credit_sales;
        """
    ),
    
    # =========================================================================
    # VERSION 2.3.0 - OPTIMIZED INDEXES
    # =========================================================================
    Migration(
        version="2.3.0",
        name="Add Optimized Indexes",
        description="Create optimized indexes for better query performance",
        up_sql="""
            CREATE INDEX IF NOT EXISTS idx_products_category_price ON products(category, price);
            CREATE INDEX IF NOT EXISTS idx_products_name_price ON products(name, price);
            CREATE INDEX IF NOT EXISTS idx_products_stock_low ON products(stock, low_stock);
            CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales(customer_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_status_date ON sales(status, created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_payment_type ON sales(payment_type);
            CREATE INDEX IF NOT EXISTS idx_sale_items_product_sale ON sale_items(product_name, sale_id);
            CREATE INDEX IF NOT EXISTS idx_sale_items_sale_product ON sale_items(sale_id, product_name);
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
            CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
            CREATE INDEX IF NOT EXISTS idx_customers_points ON customers(points);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_type_date ON stock_movements(type, created_at);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_product_date ON stock_movements(product_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_expenses_category_date ON expenses(category, expense_date);
            CREATE INDEX IF NOT EXISTS idx_expenses_amount ON expenses(amount);
            CREATE INDEX IF NOT EXISTS idx_credit_sales_status_date ON credit_sales(status, due_date);
            CREATE INDEX IF NOT EXISTS idx_credit_sales_customer_status ON credit_sales(customer_id, status);
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_date ON supplier_payments(payment_date DESC);
            CREATE INDEX IF NOT EXISTS idx_supplier_payments_type ON supplier_payments(payment_type);
            CREATE INDEX IF NOT EXISTS idx_product_locations_quantity ON product_locations(quantity);
            CREATE INDEX IF NOT EXISTS idx_product_locations_expire ON product_locations(expire_date);
            CREATE INDEX IF NOT EXISTS idx_activity_username ON user_activity_log(username);
            CREATE INDEX IF NOT EXISTS idx_activity_created ON user_activity_log(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_points_log_customer_date ON customer_points_log(customer_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_points_log_type ON customer_points_log(type);
            CREATE INDEX IF NOT EXISTS idx_purchase_orders_supplier ON purchase_orders(supplier_id);
            CREATE INDEX IF NOT EXISTS idx_purchase_orders_status ON purchase_orders(status);
            CREATE INDEX IF NOT EXISTS idx_purchase_orders_date ON purchase_orders(order_date DESC);
            CREATE INDEX IF NOT EXISTS idx_po_items_product ON purchase_order_items(product_id);
            CREATE INDEX IF NOT EXISTS idx_po_items_po ON purchase_order_items(po_id);
        """,
        down_sql=""
    ),
    
    # =========================================================================
    # VERSION 2.4.0 - BATCH-AWARE PRODUCT LOCATIONS
    # =========================================================================
    Migration(
        version="2.4.0",
        name="Batch-Aware Product Locations",
        description="Add batch_no and expire_date to UNIQUE constraint for product_locations",
        up_sql="""
            CREATE TABLE product_locations_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                location TEXT NOT NULL,
                batch_no TEXT,
                expire_date TEXT,
                quantity INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
                UNIQUE(product_id, location, batch_no, expire_date)
            );
            
            INSERT INTO product_locations_new (product_id, location, batch_no, expire_date, quantity, last_updated)
            SELECT product_id, location, 
                   COALESCE(batch_no, '') as batch_no,
                   expire_date, quantity, last_updated
            FROM product_locations;
            
            DROP TABLE product_locations;
            ALTER TABLE product_locations_new RENAME TO product_locations;
            
            CREATE INDEX idx_pl_fifo ON product_locations(product_id, expire_date ASC, last_updated ASC);
            CREATE INDEX idx_pl_product ON product_locations(product_id);
            CREATE INDEX idx_pl_location ON product_locations(location);
            CREATE INDEX idx_pl_expiry ON product_locations(expire_date);
        """,
        down_sql="",
        dependencies=["2.3.0"]
    ),

    # =========================================================================
    # VERSION 2.5.0 - EXPIRY ALERT TRACKING
    # =========================================================================
    Migration(
        version="2.5.0",
        name="Expiry Alert Tracking",
        description="Add table to track expired stock alerts and warnings",
        up_sql="""
            CREATE TABLE IF NOT EXISTS expiry_alerts_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT,
                location TEXT,
                batch_no TEXT,
                expire_date TEXT,
                quantity INTEGER,
                alert_type TEXT,
                message TEXT,
                sale_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_resolved INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_expiry_alerts_product ON expiry_alerts_log(product_id);
            CREATE INDEX IF NOT EXISTS idx_expiry_alerts_created ON expiry_alerts_log(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_expiry_alerts_resolved ON expiry_alerts_log(is_resolved);
        """,
        down_sql="""
            DROP TABLE IF EXISTS expiry_alerts_log;
        """,
        dependencies=["2.4.0"]
    ),

    # =========================================================================
    # VERSION 2.6.0 - FAVOURITE PRODUCTS
    # =========================================================================
    Migration(
        version="2.6.0",
        name="Favourite Products",
        description="Add is_favourite column to products table for marking favourite items",
        up_sql="""
            ALTER TABLE products ADD COLUMN is_favourite INTEGER DEFAULT 0;
            CREATE INDEX IF NOT EXISTS idx_products_favourite ON products(is_favourite);
        """,
        down_sql="",
        dependencies=["2.5.0"]
    ),
    
    # =========================================================================
    # VERSION 2.7.0 - CATEGORY GROUPS
    # =========================================================================
    Migration(
        version="2.7.0",
        name="Category Groups",
        description="Add category groups for organizing categories",
        up_sql="""
            CREATE TABLE IF NOT EXISTS category_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                icon TEXT,
                color TEXT,
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            ALTER TABLE categories ADD COLUMN group_id INTEGER REFERENCES category_groups(id) ON DELETE SET NULL;
            
            CREATE INDEX IF NOT EXISTS idx_categories_group ON categories(group_id);
            CREATE INDEX IF NOT EXISTS idx_category_groups_active ON category_groups(is_active);
            
            INSERT OR IGNORE INTO category_groups (name, description, sort_order) VALUES 
            ('Stationery', 'Pens, pencils, paper, books, rulers, erasers', 1);
            
            UPDATE categories SET group_id = (SELECT id FROM category_groups WHERE name = 'Stationery')
            WHERE LOWER(name) IN ('pen', 'pencil', 'paper', 'book', 'ruler', 'eraser', 'stapler', 'scissors', 'tape', 'glue', 'marker', 'highlight', 'notebook', 'journal', 'envelope', 'folder', 'binder', 'clip', 'pin', 'sticky note');
        """,
        down_sql="""
            DROP TABLE IF EXISTS category_groups;
            ALTER TABLE categories DROP COLUMN group_id;
        """
    ),
    
    # =========================================================================
    # VERSION 2.8.0 - FAVOURITE CATEGORIES & GROUPS
    # =========================================================================
    Migration(
        version="2.8.0",
        name="Favourite Categories & Groups",
        description="Add is_favorite column to categories and category_groups tables",
        up_sql="""
            ALTER TABLE categories ADD COLUMN is_favorite INTEGER DEFAULT 0;
            ALTER TABLE category_groups ADD COLUMN is_favorite INTEGER DEFAULT 0;
            CREATE INDEX IF NOT EXISTS idx_categories_favorite ON categories(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_category_groups_favorite ON category_groups(is_favorite);
        """,
        down_sql="""
            DROP INDEX IF EXISTS idx_categories_favorite;
            DROP INDEX IF EXISTS idx_category_groups_favorite;
        """,
        dependencies=["2.7.0"]
    ),
    
    Migration(
        version="2.9.0",
        name="Add Receipt Settings",
        description="Add receipt-related settings to database",
        up_sql="""
            INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('receipt_font_name', 'Courier New'),
            ('receipt_font_size', '9'),
            ('show_logo_on_receipt', '1'),
            ('show_barcode', '0'),
            ('show_qr', '0'),
            ('print_mode', 'gdi');
        """,
        down_sql="""
            DELETE FROM settings WHERE key IN (
                'receipt_font_name', 'receipt_font_size', 
                'show_logo_on_receipt', 'show_barcode', 
                'show_qr', 'print_mode'
            );
        """,
        dependencies=["2.8.0"]
    ),
    
    # =========================================================================
    # VERSION 3.0.0 - ENHANCED CATEGORY SYSTEM (FIXED)
    # =========================================================================
    Migration(
        version="3.0.0",
        name="Enhanced Category System",
        description="Add enhanced category system with parent-child, colors, icons, images, and status",
        up_sql="""
            -- ============================================================
            -- FIX: Add slug column without UNIQUE constraint
            -- SQLite doesn't support ALTER TABLE ADD COLUMN with UNIQUE
            -- ============================================================
            
            -- Add slug column (without UNIQUE)
            ALTER TABLE categories ADD COLUMN slug TEXT;
            
            -- Add other columns
            ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id) ON DELETE SET NULL;
            ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0;
            ALTER TABLE categories ADD COLUMN color TEXT DEFAULT '#6c5ce7';
            ALTER TABLE categories ADD COLUMN icon TEXT DEFAULT '📁';
            ALTER TABLE categories ADD COLUMN image TEXT;
            ALTER TABLE categories ADD COLUMN status TEXT DEFAULT 'active';
            ALTER TABLE categories ADD COLUMN code TEXT;
            ALTER TABLE categories ADD COLUMN notes TEXT;
            ALTER TABLE categories ADD COLUMN is_system INTEGER DEFAULT 0;
            ALTER TABLE categories ADD COLUMN is_favorite INTEGER DEFAULT 0;
            ALTER TABLE categories ADD COLUMN group_id INTEGER;
            ALTER TABLE categories ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            
            -- Update existing categories with slugs
            UPDATE categories SET 
                slug = LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    TRIM(COALESCE(name, 'category')), ' ', '-'), '(', ''), ')', ''), '/', '-'), '&', 'and')),
                status = COALESCE(status, 'active'),
                sort_order = COALESCE(sort_order, id),
                updated_at = CURRENT_TIMESTAMP
            WHERE slug IS NULL OR slug = '';
            
            -- Handle duplicate slugs by adding numbers
            UPDATE categories SET slug = slug || '-' || id 
            WHERE slug IN (SELECT slug FROM categories GROUP BY slug HAVING COUNT(*) > 1);
            
            -- Create unique index for slug (instead of UNIQUE constraint)
            CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_slug_unique ON categories(slug);
            
            -- Create other indexes
            CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
            CREATE INDEX IF NOT EXISTS idx_categories_status ON categories(status);
            CREATE INDEX IF NOT EXISTS idx_categories_sort ON categories(sort_order);
            CREATE INDEX IF NOT EXISTS idx_categories_code ON categories(code);
            CREATE INDEX IF NOT EXISTS idx_categories_favorite ON categories(is_favorite);
            CREATE INDEX IF NOT EXISTS idx_categories_group ON categories(group_id);
            
            -- Create new tables
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
            );
            
            CREATE TABLE IF NOT EXISTS category_stats (
                category_id INTEGER PRIMARY KEY,
                product_count INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS category_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                user_id INTEGER,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            );
            
            -- Insert default categories if none exist
            INSERT OR IGNORE INTO categories (name, slug, icon, color, status, is_system, sort_order) VALUES 
            ('General', 'general', '📁', '#6c5ce7', 'active', 1, 1),
            ('Food', 'food', '🍔', '#e74c3c', 'active', 0, 2),
            ('Drinks', 'drinks', '🥤', '#3498db', 'active', 0, 3),
            ('Snacks', 'snacks', '🍿', '#f39c12', 'active', 0, 4),
            ('Coffee', 'coffee', '☕', '#795548', 'active', 0, 5);
        """,
        down_sql="""
            DROP TABLE IF EXISTS category_stats;
            DROP TABLE IF EXISTS category_groups;
            DROP TABLE IF EXISTS category_activity_log;
            DROP INDEX IF EXISTS idx_categories_slug_unique;
        """
    )
]
