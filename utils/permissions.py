# utils/permissions.py
from enum import Enum
from models.database import connect_db
from loguru import logger
from utils.db_compat import table_exists


class Permission(Enum):
    # Dashboard
    VIEW_DASHBOARD = "dashboard"
    
    # Sales
    VIEW_SALES = "sales"
    CREATE_SALE = "create_sale"
    EDIT_SALE = "edit_sale"
    DELETE_SALE = "delete_sale"
    REFUND_SALE = "refund_sale"
    
    # Sales Summary
    VIEW_SALES_SUMMARY = "sales_summary"
    
    # Products
    VIEW_PRODUCTS = "products"
    ADD_PRODUCT = "add_product"
    EDIT_PRODUCT = "edit_product"
    DELETE_PRODUCT = "delete_product"
    
    # AI Pages  <-- NEW
    VIEW_AI_PAGES = "ai_pages"
    
    # Inventory
    VIEW_INVENTORY = "inventory"
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    STOCK_ADJUSTMENT = "adjustment"
    
    # Receipts
    VIEW_RECEIPTS = "receipts"
    PRINT_RECEIPT = "print_receipt"
    REFUND_RECEIPT = "refund_receipt"
    
    # Customers
    VIEW_CUSTOMERS = "customers"
    ADD_CUSTOMER = "add_customer"
    EDIT_CUSTOMER = "edit_customer"
    DELETE_CUSTOMER = "delete_customer"
    
    # Expense
    VIEW_EXPENSE = "expense"
    ADD_EXPENSE = "add_expense"
    EDIT_EXPENSE = "edit_expense"
    DELETE_EXPENSE = "delete_expense"
    MANAGE_EXPENSE_CATEGORIES = "manage_expense_categories"
    
    # Reports
    VIEW_REPORTS = "reports"
    
    # Credit
    VIEW_CREDIT = "credit"
    CREATE_CREDIT_SALE = "credit_sale"
    COLLECT_PAYMENT = "payment_collection"
    
    # Users & Settings
    VIEW_USERS = "users"
    ADD_USER = "add_user"
    EDIT_USER = "edit_user"
    DELETE_USER = "delete_user"
    VIEW_SETTINGS = "settings"
    EDIT_SETTINGS = "edit_settings"
    
    # Backup
    BACKUP = "backup"
    RESTORE = "restore"
    FACTORY_RESET = "factory_reset"


class PermissionManager:
    @staticmethod
    def get_role_permissions(role_name):
        """Get permissions for a specific role"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT permissions FROM user_roles WHERE name = ?", (role_name,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return set(row[0].split(','))
        return set()
    
    @staticmethod
    def get_user_permissions(user_id):
        """Get permissions for a specific user"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.role, u.permissions, ur.permissions as role_permissions
            FROM users u
            LEFT JOIN user_roles ur ON u.role = ur.name
            WHERE u.id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return set()
        
        role, user_perms, role_perms = row
        
        # Start with role permissions
        if role_perms:
            permissions = set(role_perms.split(','))
        else:
            permissions = set()
        
        # Add user-specific permissions (override)
        if user_perms:
            user_perms_set = set(user_perms.split(','))
            permissions.update(user_perms_set)
        
        return permissions
    
    @staticmethod
    def user_has_permission(user_id, permission):
        """Check if user has a specific permission"""
        permissions = PermissionManager.get_user_permissions(user_id)
        return permission.value in permissions
    
    @staticmethod
    def user_can_view_page(user_id, page_name):
        """Check if user can view a specific page"""
        page_permissions = {
            "dashboard": Permission.VIEW_DASHBOARD,
            "sales_summary": Permission.VIEW_SALES_SUMMARY,
            "sales": Permission.VIEW_SALES,
            "products": Permission.VIEW_PRODUCTS,
            "ai_pages": Permission.VIEW_AI_PAGES,  # <-- NEW
            "inventory": Permission.VIEW_INVENTORY,
            "receipts": Permission.VIEW_RECEIPTS,
            "customers": Permission.VIEW_CUSTOMERS,
            "expense": Permission.VIEW_EXPENSE,
            "reports": Permission.VIEW_REPORTS,
            "credit": Permission.VIEW_CREDIT,
            "users": Permission.VIEW_USERS,
            "settings": Permission.VIEW_SETTINGS,
        }
        
        if page_name in page_permissions:
            return PermissionManager.user_has_permission(user_id, page_permissions[page_name])
        return False


# Role-based permission sets
ROLE_PERMISSIONS = {
    "Admin": {
        "permissions": [
            Permission.VIEW_DASHBOARD,
            Permission.VIEW_SALES, Permission.CREATE_SALE, Permission.EDIT_SALE,
            Permission.DELETE_SALE, Permission.REFUND_SALE,
            Permission.VIEW_SALES_SUMMARY,
            Permission.VIEW_PRODUCTS, Permission.ADD_PRODUCT, Permission.EDIT_PRODUCT, Permission.DELETE_PRODUCT,
            Permission.VIEW_AI_PAGES,
            Permission.VIEW_INVENTORY, Permission.STOCK_IN, Permission.STOCK_OUT, Permission.STOCK_ADJUSTMENT,
            Permission.VIEW_RECEIPTS, Permission.PRINT_RECEIPT, Permission.REFUND_RECEIPT,
            Permission.VIEW_CUSTOMERS, Permission.ADD_CUSTOMER, Permission.EDIT_CUSTOMER, Permission.DELETE_CUSTOMER,
            Permission.VIEW_EXPENSE, Permission.ADD_EXPENSE, Permission.EDIT_EXPENSE, Permission.DELETE_EXPENSE,
            Permission.MANAGE_EXPENSE_CATEGORIES,
            Permission.VIEW_REPORTS,
            Permission.VIEW_CREDIT, Permission.CREATE_CREDIT_SALE, Permission.COLLECT_PAYMENT,
            Permission.VIEW_USERS, Permission.ADD_USER, Permission.EDIT_USER, Permission.DELETE_USER,
            Permission.VIEW_SETTINGS, Permission.EDIT_SETTINGS,
            Permission.BACKUP, Permission.RESTORE, Permission.FACTORY_RESET,
        ]
    },
    "Manager": {
        "permissions": [
            Permission.VIEW_DASHBOARD,
            Permission.VIEW_SALES, Permission.CREATE_SALE, Permission.EDIT_SALE, Permission.REFUND_SALE,
            Permission.VIEW_SALES_SUMMARY,
            Permission.VIEW_PRODUCTS, Permission.ADD_PRODUCT, Permission.EDIT_PRODUCT, Permission.DELETE_PRODUCT,
            Permission.VIEW_AI_PAGES,
            Permission.VIEW_INVENTORY, Permission.STOCK_IN, Permission.STOCK_OUT, Permission.STOCK_ADJUSTMENT,
            Permission.VIEW_RECEIPTS, Permission.PRINT_RECEIPT, Permission.REFUND_RECEIPT,
            Permission.VIEW_CUSTOMERS, Permission.ADD_CUSTOMER, Permission.EDIT_CUSTOMER,
            Permission.VIEW_EXPENSE, Permission.ADD_EXPENSE, Permission.EDIT_EXPENSE, Permission.DELETE_EXPENSE,
            Permission.MANAGE_EXPENSE_CATEGORIES,
            Permission.VIEW_REPORTS,
            Permission.VIEW_CREDIT, Permission.CREATE_CREDIT_SALE, Permission.COLLECT_PAYMENT,
            Permission.VIEW_SETTINGS, Permission.BACKUP,
        ]
    },
    "Cashier": {
        "permissions": [
            Permission.VIEW_SALES, Permission.CREATE_SALE,
            Permission.VIEW_RECEIPTS, Permission.PRINT_RECEIPT, Permission.REFUND_RECEIPT,
            Permission.VIEW_CUSTOMERS, Permission.ADD_CUSTOMER,
            Permission.VIEW_CREDIT, Permission.CREATE_CREDIT_SALE, Permission.COLLECT_PAYMENT,
        ]
    },
    "Viewer": {
        "permissions": [
            Permission.VIEW_DASHBOARD,
            Permission.VIEW_SALES_SUMMARY,
            Permission.VIEW_PRODUCTS,
            Permission.VIEW_INVENTORY,
            Permission.VIEW_RECEIPTS,
            Permission.VIEW_CUSTOMERS,
            Permission.VIEW_REPORTS,
            Permission.VIEW_CREDIT,
        ]
    }
}


ROLE_DESCRIPTIONS = {
    "Admin": "Full access to every page and action",
    "Manager": "Manage daily operations without user deletion, restore, or factory reset",
    "Cashier": "Process sales, print receipts, refund receipts, and manage sale customers",
    "Viewer": "Read-only access to dashboards, lists, receipts, reports, and credit",
}


def update_role_permissions_in_db():
    """Update role permissions in database (runs automatically on import)"""
    try:
        conn = connect_db()
        cursor = conn.cursor()
        
        # ✅ Check if user_roles table exists
        if not table_exists(cursor, "user_roles"):
            logger.warning("user_roles table not found, skipping permission update")
            conn.close()
            return
        
        updated_count = 0
        for role_name, role_data in ROLE_PERMISSIONS.items():
            permissions_str = ','.join([p.value for p in role_data["permissions"]])
            description = ROLE_DESCRIPTIONS.get(role_name, f"{role_name} role")
            
            cursor.execute("SELECT permissions FROM user_roles WHERE name = ?", (role_name,))
            row = cursor.fetchone()
            
            if row:
                current_perms = row[0] or ''
                if current_perms != permissions_str:
                    cursor.execute("""
                        UPDATE user_roles
                        SET description = ?, permissions = ?
                        WHERE name = ?
                    """, (description, permissions_str, role_name))
                    updated_count += 1
                    logger.info(f"Updated permissions for role: {role_name}")
            else:
                # Role doesn't exist, insert it
                cursor.execute("""
                    INSERT INTO user_roles (name, description, permissions, is_system)
                    VALUES (?, ?, ?, ?)
                """, (role_name, description, permissions_str, 1 if role_name == "Admin" else 0))
                updated_count += 1
                logger.info(f"Inserted role: {role_name}")
        
        conn.commit()
        conn.close()
        
        if updated_count > 0:
            logger.info(f"Updated {updated_count} default role permission set(s)")
        else:
            logger.debug("All default role permission sets are up to date")
        
    except Exception as e:
        logger.warning(f"Could not update role permissions: {e}")


def get_permission_description(permission):
    """Get human-readable description for a permission"""
    descriptions = {
        Permission.VIEW_DASHBOARD: "View Dashboard",
        Permission.VIEW_SALES: "View Sales",
        Permission.CREATE_SALE: "Create Sale",
        Permission.EDIT_SALE: "Edit Sale",
        Permission.DELETE_SALE: "Delete Sale",
        Permission.REFUND_SALE: "Refund Sale",
        Permission.VIEW_SALES_SUMMARY: "View Sales Summary",
        Permission.VIEW_PRODUCTS: "View Products",
        Permission.ADD_PRODUCT: "Add Product",
        Permission.EDIT_PRODUCT: "Edit Product",
        Permission.DELETE_PRODUCT: "Delete Product",
        Permission.VIEW_AI_PAGES: "View AI Pages",  # <-- NEW
        Permission.VIEW_INVENTORY: "View Inventory",
        Permission.STOCK_IN: "Stock In",
        Permission.STOCK_OUT: "Stock Out",
        Permission.STOCK_ADJUSTMENT: "Stock Adjustment",
        Permission.VIEW_RECEIPTS: "View Receipts",
        Permission.PRINT_RECEIPT: "Print Receipt",
        Permission.REFUND_RECEIPT: "Refund Receipt",
        Permission.VIEW_CUSTOMERS: "View Customers",
        Permission.ADD_CUSTOMER: "Add Customer",
        Permission.EDIT_CUSTOMER: "Edit Customer",
        Permission.DELETE_CUSTOMER: "Delete Customer",
        Permission.VIEW_EXPENSE: "View Expenses",
        Permission.ADD_EXPENSE: "Add Expense",
        Permission.EDIT_EXPENSE: "Edit Expense",
        Permission.DELETE_EXPENSE: "Delete Expense",
        Permission.MANAGE_EXPENSE_CATEGORIES: "Manage Expense Categories",
        Permission.VIEW_REPORTS: "View Reports",
        Permission.VIEW_CREDIT: "View Credit",
        Permission.CREATE_CREDIT_SALE: "Create Credit Sale",
        Permission.COLLECT_PAYMENT: "Collect Payment",
        Permission.VIEW_USERS: "View Users",
        Permission.ADD_USER: "Add User",
        Permission.EDIT_USER: "Edit User",
        Permission.DELETE_USER: "Delete User",
        Permission.VIEW_SETTINGS: "View Settings",
        Permission.EDIT_SETTINGS: "Edit Settings",
        Permission.BACKUP: "Backup Database",
        Permission.RESTORE: "Restore Database",
        Permission.FACTORY_RESET: "Factory Reset",
    }
    return descriptions.get(permission, permission.value.replace('_', ' ').title())


# ✅ AUTO-RUN on import - Client အတွက် auto update
try:
    update_role_permissions_in_db()
except Exception as e:
    logger.warning(f"Could not auto-update role permissions on import: {e}")
