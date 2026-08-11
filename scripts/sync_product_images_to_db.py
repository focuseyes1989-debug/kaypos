"""Copy existing product image files into the products table.

Run this on the Server PC after PostgreSQL is configured, because the Server PC
is the machine most likely to still have database/product_images files.
"""

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.env_loader import load_project_env


def _configure_postgres_env():
    load_project_env()
    os.environ["ZAY_POS_DB_BACKEND"] = "postgres"
    if not (os.getenv("ZAY_POS_DATABASE_URL") or os.getenv("DATABASE_URL")):
        print("SKIP: ZAY_POS_DATABASE_URL/DATABASE_URL is not configured.")
        return False
    return True


def main():
    if not _configure_postgres_env():
        return 0

    from models.database import connect_db, safe_initialize_database
    from utils.product_image_store import save_product_image_blob

    safe_initialize_database()
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, image
        FROM products
        WHERE image IS NOT NULL
          AND image != ''
          AND image_data IS NULL
        ORDER BY id
    """)
    rows = cursor.fetchall()

    synced = 0
    skipped = 0
    for product_id, image_path in rows:
        cursor.execute("SELECT image_data FROM products WHERE id = ?", (product_id,))
        before = cursor.fetchone()
        save_product_image_blob(cursor, product_id, image_path)
        cursor.execute("SELECT image_data FROM products WHERE id = ?", (product_id,))
        after = cursor.fetchone()
        if (not before or before[0] is None) and after and after[0] is not None:
            synced += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()
    print(f"Product image sync complete. synced={synced}, skipped={skipped}, checked={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
