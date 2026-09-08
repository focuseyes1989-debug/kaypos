"""Route desktop variant changes through the shared batch-aware stock service."""
from PyQt6.QtWidgets import QInputDialog, QMessageBox
from models.database import connect_db
from server import cashier_service


def handle_variant_operation(dialog, product_id, operation, quantity, location, reason,
                             actor='', notes='', to_location=None, location_only=False):
    conn=connect_db()
    try:
        cursor=conn.cursor()
        cursor.execute('SELECT id,size,color,stock FROM product_variants WHERE product_id=? AND COALESCE(active,1)=1 ORDER BY id',(product_id,))
        rows=cursor.fetchall()
    finally:
        conn.close()
    if not rows:
        return False
    if location_only:
        QMessageBox.warning(dialog,'Variant stock','Use a variant transfer to move stock between locations.')
        return True
    labels=[f"#{row[0]} {' / '.join(str(v) for v in row[1:3] if v)} | Stock: {row[3]}" for row in rows]
    chosen,ok=QInputDialog.getItem(dialog,operation,'Select the variant for this operation:',labels,0,False)
    if not ok:return True
    variant_id,_,_,stock=rows[labels.index(chosen)]
    if QMessageBox.question(dialog,operation,f'{chosen}\n{operation} quantity: {quantity}\nLocation: {location}\nContinue?') != QMessageBox.StandardButton.Yes:
        return True
    try:
        if operation=='Stock Out':
            cashier_service.adjust_stock(product_id=product_id,variant_id=variant_id,adjustment=-int(quantity),location=location,restrict_location=True,reason=reason,issued_by=actor,notes=notes)
        elif operation=='Adjustment':
            cashier_service.set_stock_quantity(product_id=product_id,variant_id=variant_id,new_quantity=int(quantity),expected_stock=int(stock),location=location,reason=reason,adjusted_by=actor,notes=notes)
        else:
            cashier_service.transfer_stock(product_id=product_id,variant_id=variant_id,quantity=int(quantity),from_location=location,to_location=to_location,reason=reason,created_by=actor,notes=notes)
        QMessageBox.information(dialog,operation,'Variant stock and batch records updated.')
        dialog.accept()
    except Exception as exc:
        QMessageBox.warning(dialog,operation,str(exc))
    return True
