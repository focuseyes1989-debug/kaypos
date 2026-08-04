# ui/products_page/product_service.py
from PyQt6.QtCore import QDate
from models.database import connect_db
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from loguru import logger
from utils.activity_logger import log_activity
import csv


class ProductService:
    def __init__(self, parent=None):
        self.parent = parent

    def load_products(self, page=1, page_size=50, search_text="", category=""):
        use_category = category != "All Categories" and category != "အားလုံး"
        conn = connect_db()
        cursor = conn.cursor()

        count_params = []
        count_where = []
        if use_category:
            count_where.append("category = ?")
            count_params.append(category)
        if search_text:
            like = f'%{search_text}%'
            count_where.append("(LOWER(name) LIKE ? OR LOWER(sku) LIKE ? OR LOWER(barcode) LIKE ?)")
            count_params.extend([like, like, like])

        count_sql = "SELECT COUNT(*) FROM products"
        if count_where:
            count_sql += " WHERE " + " AND ".join(count_where)
        cursor.execute(count_sql, count_params)
        total_items = cursor.fetchone()[0]

        offset = (page - 1) * page_size
        select_params = []
        where_clauses = []
        if use_category:
            where_clauses.append("category = ?")
            select_params.append(category)
        if search_text:
            like = f'%{search_text}%'
            where_clauses.append("(LOWER(name) LIKE ? OR LOWER(sku) LIKE ? OR LOWER(barcode) LIKE ?)")
            select_params.extend([like, like, like])

        select_sql = """
            SELECT id, name, price, COALESCE(stock, 0) as stock, COALESCE(low_stock, 0) as low_stock, 
                   COALESCE(sold_by, 'Each') as sold_by, image
            FROM products
        """
        if where_clauses:
            select_sql += " WHERE " + " AND ".join(where_clauses)
        select_sql += " ORDER BY name LIMIT ? OFFSET ?"
        cursor.execute(select_sql, select_params + [page_size, offset])
        rows = cursor.fetchall()
        conn.close()
        return rows, total_items

    def filter_by_type(self, filter_type, page=1, page_size=50):
        conn = connect_db()
        cursor = conn.cursor()

        if filter_type == 'out_of_stock':
            cursor.execute("SELECT COUNT(*) FROM products WHERE (sold_by IS NULL OR sold_by != 'Service') AND COALESCE(stock, 0) = 0")
            total = cursor.fetchone()[0]
            offset = (page - 1) * page_size
            cursor.execute("""
                SELECT id, name, price, COALESCE(stock, 0) as stock, COALESCE(low_stock, 0) as low_stock,
                       COALESCE(sold_by, 'Each') as sold_by, image
                FROM products WHERE (sold_by IS NULL OR sold_by != 'Service') AND COALESCE(stock, 0) = 0
                ORDER BY name LIMIT ? OFFSET ?
            """, (page_size, offset))
            rows = cursor.fetchall()
        elif filter_type == 'low_stock':
            cursor.execute("""
                SELECT COUNT(*) FROM products 
                WHERE (sold_by IS NULL OR sold_by != 'Service') 
                  AND COALESCE(stock, 0) > 0 
                  AND COALESCE(stock, 0) <= COALESCE(low_stock, 0)
            """)
            total = cursor.fetchone()[0]
            offset = (page - 1) * page_size
            cursor.execute("""
                SELECT id, name, price, COALESCE(stock, 0) as stock, COALESCE(low_stock, 0) as low_stock,
                       COALESCE(sold_by, 'Each') as sold_by, image
                FROM products 
                WHERE (sold_by IS NULL OR sold_by != 'Service') 
                  AND COALESCE(stock, 0) > 0 
                  AND COALESCE(stock, 0) <= COALESCE(low_stock, 0)
                ORDER BY name LIMIT ? OFFSET ?
            """, (page_size, offset))
            rows = cursor.fetchall()
        elif filter_type == 'expiring_soon':
            today = QDate.currentDate()
            today_str = today.toString("yyyy-MM-dd")
            week_later_str = today.addDays(7).toString("yyyy-MM-dd")
            cursor.execute("SELECT COUNT(*) FROM products WHERE expire_date >= ? AND expire_date <= ?", (today_str, week_later_str))
            total = cursor.fetchone()[0]
            offset = (page - 1) * page_size
            cursor.execute("""
                SELECT id, name, price, COALESCE(stock, 0) as stock, COALESCE(low_stock, 0) as low_stock,
                       COALESCE(sold_by, 'Each') as sold_by, image
                FROM products WHERE expire_date >= ? AND expire_date <= ?
                ORDER BY name LIMIT ? OFFSET ?
            """, (today_str, week_later_str, page_size, offset))
            rows = cursor.fetchall()
        elif filter_type == 'expired':
            today = QDate.currentDate()
            today_str = today.toString("yyyy-MM-dd")
            cursor.execute("SELECT COUNT(*) FROM products WHERE expire_date < ?", (today_str,))
            total = cursor.fetchone()[0]
            offset = (page - 1) * page_size
            cursor.execute("""
                SELECT id, name, price, COALESCE(stock, 0) as stock, COALESCE(low_stock, 0) as low_stock,
                       COALESCE(sold_by, 'Each') as sold_by, image
                FROM products WHERE expire_date < ?
                ORDER BY name LIMIT ? OFFSET ?
            """, (today_str, page_size, offset))
            rows = cursor.fetchall()
        else:
            rows, total = [], 0

        conn.close()
        return rows, total

    def export_products(self, rows, parent):
        """Export products to CSV with Category and Category Group"""
        if not rows:
            QMessageBox.warning(parent, "No Data", "No products to export.")
            return
        file_path, _ = QFileDialog.getSaveFileName(parent, "Export Products", "", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # Add Category and Category Group to headers
                headers = ["SKU", "Name", "Category", "Category Group", "Barcode", "Price", "Stock", "Sold By"]
                writer.writerow(headers)
                
                for row in rows:
                    conn = connect_db()
                    cursor = conn.cursor()
                    # Get sku, category, barcode, and category group
                    cursor.execute("""
                        SELECT p.sku, p.category, p.barcode, cg.name 
                        FROM products p
                        LEFT JOIN categories c ON p.category = c.name
                        LEFT JOIN category_groups cg ON c.group_id = cg.id
                        WHERE p.id=?
                    """, (row[0],))
                    prod_data = cursor.fetchone()
                    conn.close()
                    
                    if prod_data:
                        sku, category, barcode, category_group = prod_data
                        writer.writerow([
                            sku or "", 
                            row[1],  # name
                            category or "", 
                            category_group or "",  # category group
                            barcode or "", 
                            row[2],  # price
                            row[3],  # stock
                            row[5]   # sold_by
                        ])
                    else:
                        writer.writerow(["", row[1], "", "", "", row[2], row[3], row[5]])
                        
            QMessageBox.information(parent, "Success", f"Exported {len(rows)} products to {file_path}")
            logger.info(f"Exported {len(rows)} products")
        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(parent, "Error", f"Export failed: {e}")

    def import_products(self, parent, refresh_callback):
        """Import products from CSV with Category and Category Group support"""
        file_path, _ = QFileDialog.getOpenFileName(parent, "Import Products", "", "CSV Files (*.csv)")
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                header = next(reader)  # Read header
                
                # Check if header has Category Group column
                has_category_group = "Category Group" in header or "category group" in header.lower()
                
                imported = 0
                updated = 0
                errors = []
                conn = connect_db()
                cursor = conn.cursor()
                
                for row_num, row in enumerate(reader, start=2):
                    # Skip empty rows
                    if not row or all(cell.strip() == '' for cell in row):
                        continue
                        
                    # Determine column positions based on header
                    try:
                        # Basic columns (always present)
                        sku_idx = header.index("SKU") if "SKU" in header else 0
                        name_idx = header.index("Name") if "Name" in header else 1
                        category_idx = header.index("Category") if "Category" in header else 2
                        barcode_idx = header.index("Barcode") if "Barcode" in header else 4
                        price_idx = header.index("Price") if "Price" in header else 5
                        stock_idx = header.index("Stock") if "Stock" in header else 6
                        sold_by_idx = header.index("Sold By") if "Sold By" in header else 7
                        
                        # Category Group (optional)
                        if has_category_group:
                            group_idx = header.index("Category Group") if "Category Group" in header else 3
                        else:
                            group_idx = None
                            
                    except ValueError as e:
                        errors.append(f"Row {row_num}: Invalid header format - {e}")
                        continue
                    
                    # Get values
                    try:
                        sku = row[sku_idx].strip() if len(row) > sku_idx else ""
                        name = row[name_idx].strip() if len(row) > name_idx else ""
                        category = row[category_idx].strip() if len(row) > category_idx else ""
                        barcode = row[barcode_idx].strip() if len(row) > barcode_idx else ""
                        price_str = row[price_idx].strip() if len(row) > price_idx else "0"
                        stock_str = row[stock_idx].strip() if len(row) > stock_idx else "0"
                        sold_by = row[sold_by_idx].strip() if len(row) > sold_by_idx else "Each"
                        category_group = row[group_idx].strip() if group_idx is not None and len(row) > group_idx else ""
                    except IndexError:
                        errors.append(f"Row {row_num}: Insufficient columns")
                        continue
                    
                    # Validate required fields
                    if not sku and not name:
                        errors.append(f"Row {row_num}: SKU or Name is required")
                        continue
                    
                    try:
                        price = float(price_str) if price_str else 0.0
                        stock = int(stock_str) if stock_str else 0
                    except ValueError as e:
                        errors.append(f"Row {row_num}: Invalid number - {e}")
                        continue
                    
                    try:
                        # Check if product exists by SKU or name
                        if sku:
                            cursor.execute("SELECT id FROM products WHERE sku=?", (sku,))
                            existing = cursor.fetchone()
                        else:
                            # If no SKU, check by name and category
                            cursor.execute("SELECT id FROM products WHERE name=? AND category=?", (name, category))
                            existing = cursor.fetchone()
                        
                        if existing:
                            # Update existing product
                            cursor.execute("""
                                UPDATE products 
                                SET name=?, category=?, barcode=?, price=?, stock=?, sold_by=?
                                WHERE id=?
                            """, (name, category, barcode, price, stock, sold_by, existing[0]))
                            updated += 1
                            
                            # Handle category group if provided
                            if category_group and category:
                                # Check if category exists
                                cursor.execute("SELECT id FROM categories WHERE name=?", (category,))
                                cat_row = cursor.fetchone()
                                if cat_row:
                                    # Check if group exists
                                    cursor.execute("SELECT id FROM category_groups WHERE name=?", (category_group,))
                                    group_row = cursor.fetchone()
                                    if group_row:
                                        # Update category's group
                                        cursor.execute("UPDATE categories SET group_id=? WHERE id=?", (group_row[0], cat_row[0]))
                                    else:
                                        # Create new group
                                        cursor.execute("INSERT INTO category_groups (name) VALUES (?)", (category_group,))
                                        group_id = cursor.lastrowid
                                        cursor.execute("UPDATE categories SET group_id=? WHERE id=?", (group_id, cat_row[0]))
                        else:
                            # Insert new product
                            cursor.execute("""
                                INSERT INTO products (sku, name, category, barcode, price, stock, sold_by, cost, low_stock)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                            """, (sku, name, category, barcode, price, stock, sold_by))
                            imported += 1
                            product_id = cursor.lastrowid
                            
                            # Handle category group if provided
                            if category_group and category:
                                # Check if category exists
                                cursor.execute("SELECT id FROM categories WHERE name=?", (category,))
                                cat_row = cursor.fetchone()
                                if cat_row:
                                    # Check if group exists
                                    cursor.execute("SELECT id FROM category_groups WHERE name=?", (category_group,))
                                    group_row = cursor.fetchone()
                                    if group_row:
                                        # Update category's group
                                        cursor.execute("UPDATE categories SET group_id=? WHERE id=?", (group_row[0], cat_row[0]))
                                    else:
                                        # Create new group
                                        cursor.execute("INSERT INTO category_groups (name) VALUES (?)", (category_group,))
                                        group_id = cursor.lastrowid
                                        cursor.execute("UPDATE categories SET group_id=? WHERE id=?", (group_id, cat_row[0]))
                                        
                    except Exception as e:
                        errors.append(f"Row {row_num}: DB error - {e}")
                        continue
                        
                conn.commit()
                conn.close()
                
                msg = f"Imported: {imported}\nUpdated: {updated}\nErrors: {len(errors)}"
                if errors:
                    error_details = "\n".join(errors[:10])
                    if len(errors) > 10:
                        error_details += f"\n... and {len(errors)-10} more errors."
                    QMessageBox.warning(parent, "Import Completed with Errors", f"{msg}\n\nError details:\n{error_details}")
                else:
                    QMessageBox.information(parent, "Import Complete", msg)
                    
                logger.info(f"Import completed: {imported} new, {updated} updated, {len(errors)} errors")
                refresh_callback()
                
        except Exception as e:
            logger.error(f"Import failed: {e}")
            QMessageBox.critical(parent, "Error", f"Import failed: {e}")

    def log_activity(self, user_id, username, action, details):
        log_activity(user_id, username, action, details)