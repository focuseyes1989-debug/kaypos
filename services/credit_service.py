# services/credit_service.py
"""
Credit Service for managing credit sales, payments, and refunds.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from loguru import logger
from models.database import connect_db, DBContext


class CreditService:
    """Service for credit sales operations."""
    
    def __init__(self):
        self.default_due_days = 15

    def get_credit_settings(self) -> Dict[str, Any]:
        """Load credit-related settings with safe defaults."""
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM settings WHERE key IN (?, ?)",
                ("credit_due_days", "credit_limit_enabled"),
            )
            raw_settings = dict(cursor.fetchall())

            try:
                due_days = int(raw_settings.get("credit_due_days", self.default_due_days))
            except (TypeError, ValueError):
                due_days = self.default_due_days

            limit_enabled = str(
                raw_settings.get("credit_limit_enabled", "true")
            ).strip().lower() in {"1", "true", "yes", "on"}

            return {
                "credit_due_days": due_days,
                "credit_limit_enabled": limit_enabled,
            }
        except Exception as e:
            logger.error(f"Failed to load credit settings: {e}")
            return {
                "credit_due_days": self.default_due_days,
                "credit_limit_enabled": True,
            }
        finally:
            conn.close()

    def check_credit_limit(self, customer_id: int, amount: float) -> Dict[str, Any]:
        """Return whether adding ``amount`` would exceed a customer's credit limit.

        A limit of zero is treated as unlimited, matching the checkout UI.
        """
        conn = connect_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT credit_limit, current_balance FROM customers WHERE id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {
                    'success': False,
                    'exceeded': True,
                    'error': 'Customer not found',
                    'credit_limit': 0,
                    'current_balance': 0,
                    'new_balance': float(amount or 0),
                }

            credit_limit = float(row[0] or 0)
            current_balance = float(row[1] or 0)
            new_balance = current_balance + float(amount or 0)
            return {
                'success': True,
                'exceeded': credit_limit > 0 and new_balance > credit_limit,
                'credit_limit': credit_limit,
                'current_balance': current_balance,
                'new_balance': new_balance,
            }
        except Exception as e:
            logger.error(f"Failed to check credit limit: {e}")
            return {
                'success': False,
                'exceeded': True,
                'error': str(e),
                'credit_limit': 0,
                'current_balance': 0,
                'new_balance': float(amount or 0),
            }
        finally:
            conn.close()
    
    # ============================================================
    # CREDIT SALE OPERATIONS
    # ============================================================
    
    def create_credit_sale(self, customer_id: int, invoice_no: str, total_amount: float,
                          paid_amount: float = 0, sale_id: int = None,
                          due_date: str = None, notes: str = None,
                          sale_date: str = None, cursor=None, conn=None) -> Dict:
        """
        Create a new credit sale.
        
        Args:
            customer_id: Customer ID
            invoice_no: Invoice number
            total_amount: Total amount
            paid_amount: Amount paid at the time of sale
            sale_id: Optional sale ID reference
            due_date: Optional due date (default: +15 days)
            notes: Optional notes
            
        Returns:
            Dict with success status and credit_sale_id
        """
        total_amount = float(total_amount or 0)
        paid_amount = float(paid_amount or 0)
        if total_amount <= 0:
            return {'success': False, 'error': 'Credit sale amount must be greater than zero'}
        if paid_amount < 0 or paid_amount > total_amount:
            return {'success': False, 'error': 'Paid amount must be between zero and the total amount'}

        if not due_date:
            due_date = (datetime.now() + timedelta(days=self.default_due_days)).strftime("%Y-%m-%d")
        if not sale_date:
            sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        owns_connection = conn is None
        if owns_connection:
            conn = connect_db()
        if cursor is None:
            cursor = conn.cursor()
        
        try:
            balance_amount = total_amount - paid_amount
            status = 'paid' if balance_amount == 0 else ('partial' if paid_amount > 0 else 'pending')
            cursor.execute("""
                INSERT INTO credit_sales 
                (invoice_no, customer_id, total_amount, paid_amount, balance_amount, 
                 sale_date, due_date, status, notes, sale_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (invoice_no, customer_id, total_amount, paid_amount, balance_amount,
                  sale_date, due_date, status, notes, sale_id))
            
            credit_sale_id = cursor.lastrowid
            
            # Update customer current balance
            cursor.execute("""
                UPDATE customers 
                SET current_balance = current_balance + ?
                WHERE id = ?
            """, (balance_amount, customer_id))
            
            if owns_connection:
                conn.commit()
            
            return {
                'success': True,
                'credit_sale_id': credit_sale_id,
                'message': 'Credit sale created successfully'
            }
            
        except Exception as e:
            if owns_connection:
                conn.rollback()
            logger.error(f"Failed to create credit sale: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            if owns_connection:
                conn.close()
    
    def get_credit_sale(self, credit_sale_id: int) -> Optional[Dict]:
        """Get credit sale details by ID."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    cs.id, cs.invoice_no, cs.customer_id, c.name as customer_name,
                    cs.total_amount, cs.paid_amount, cs.balance_amount,
                    cs.sale_date, cs.due_date, cs.status, cs.notes, cs.sale_id,
                    cs.created_at
                FROM credit_sales cs
                LEFT JOIN customers c ON cs.customer_id = c.id
                WHERE cs.id = ?
            """, (credit_sale_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'invoice_no': row[1],
                'customer_id': row[2],
                'customer_name': row[3],
                'total_amount': row[4],
                'paid_amount': row[5],
                'balance_amount': row[6],
                'sale_date': row[7],
                'due_date': row[8],
                'status': row[9],
                'notes': row[10],
                'sale_id': row[11],
                'created_at': row[12]
            }
            
        except Exception as e:
            logger.error(f"Failed to get credit sale: {e}")
            return None
        finally:
            conn.close()
    
    def get_credit_sale_by_invoice(self, invoice_no: str) -> Optional[Dict]:
        """Get credit sale by invoice number."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    cs.id, cs.invoice_no, cs.customer_id, c.name as customer_name,
                    cs.total_amount, cs.paid_amount, cs.balance_amount,
                    cs.sale_date, cs.due_date, cs.status, cs.notes, cs.sale_id,
                    cs.created_at
                FROM credit_sales cs
                LEFT JOIN customers c ON cs.customer_id = c.id
                WHERE cs.invoice_no = ?
            """, (invoice_no,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'invoice_no': row[1],
                'customer_id': row[2],
                'customer_name': row[3],
                'total_amount': row[4],
                'paid_amount': row[5],
                'balance_amount': row[6],
                'sale_date': row[7],
                'due_date': row[8],
                'status': row[9],
                'notes': row[10],
                'sale_id': row[11],
                'created_at': row[12]
            }
            
        except Exception as e:
            logger.error(f"Failed to get credit sale by invoice: {e}")
            return None
        finally:
            conn.close()
    
    def get_customer_credit_sales(self, customer_id: int, status: str = None) -> List[Dict]:
        """Get all credit sales for a customer."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT 
                    id, invoice_no, total_amount, paid_amount, balance_amount,
                    sale_date, due_date, status, notes, sale_id, created_at
                FROM credit_sales
                WHERE customer_id = ?
            """
            params = [customer_id]
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'invoice_no': row[1],
                    'total_amount': row[2],
                    'paid_amount': row[3],
                    'balance_amount': row[4],
                    'sale_date': row[5],
                    'due_date': row[6],
                    'status': row[7],
                    'notes': row[8],
                    'sale_id': row[9],
                    'created_at': row[10]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get customer credit sales: {e}")
            return []
        finally:
            conn.close()
    
    # ============================================================
    # PAYMENT OPERATIONS
    # ============================================================
    
    def make_payment(self, credit_sale_id: int, amount: float, 
                     payment_method: str = 'Cash', reference_no: str = None,
                     note: str = None, payment_date: str = None) -> Dict:
        """
        Make a payment towards a credit sale.
        
        Args:
            credit_sale_id: Credit sale ID
            amount: Payment amount
            payment_method: Payment method
            reference_no: Optional reference number
            note: Optional note
            
        Returns:
            Dict with success status
        """
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN IMMEDIATE")
            
            # Get credit sale details
            cursor.execute("""
                SELECT customer_id, total_amount, paid_amount, balance_amount, status
                FROM credit_sales
                WHERE id = ?
            """, (credit_sale_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return {'success': False, 'error': 'Credit sale not found'}
            
            customer_id, total_amount, paid_amount, balance_amount, status = row
            
            if status == 'refunded':
                conn.rollback()
                return {'success': False, 'error': 'Credit sale has been refunded'}
            
            if amount > balance_amount:
                conn.rollback()
                return {'success': False, 'error': f'Payment amount exceeds balance ({balance_amount})'}
            
            # Update credit sale
            new_paid_amount = paid_amount + amount
            new_balance_amount = balance_amount - amount
            
            if new_balance_amount <= 0:
                new_status = 'paid'
                new_balance_amount = 0
            else:
                new_status = 'partial'
            
            cursor.execute("""
                UPDATE credit_sales
                SET paid_amount = ?, balance_amount = ?, status = ?
                WHERE id = ?
            """, (new_paid_amount, new_balance_amount, new_status, credit_sale_id))
            
            # Record payment
            cursor.execute("""
                INSERT INTO credit_payments 
                (credit_sale_id, customer_id, amount, payment_date, payment_method, reference_no, note)
                VALUES (?, ?, ?, COALESCE(NULLIF(?, ''), CAST(CURRENT_TIMESTAMP AS TEXT)), ?, ?, ?)
            """, (credit_sale_id, customer_id, amount, payment_date, payment_method, reference_no, note))
            
            # Update customer current balance
            cursor.execute("""
                UPDATE customers 
                SET current_balance = current_balance - ?
                WHERE id = ?
            """, (amount, customer_id))
            
            conn.commit()
            
            return {
                'success': True,
                'message': 'Payment recorded successfully',
                'new_balance': new_balance_amount,
                'status': new_status
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to make payment: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def record_credit_payment(
        self,
        customer_id: int,
        amount: float,
        credit_sale_id: int = None,
        payment_date: str = None,
        payment_method: str = 'Cash',
        reference_no: str = None,
        note: str = None,
        auto_allocate: bool = False,
    ) -> Dict:
        """Compatibility wrapper used by payment dialogs.

        If credit_sale_id is provided, payment is applied to that invoice.
        If auto_allocate is True, payment is allocated to oldest outstanding invoices.
        """
        try:
            amount = float(amount or 0)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid payment amount'}

        if amount <= 0:
            return {'success': False, 'error': 'Payment amount must be greater than zero'}

        if credit_sale_id:
            return self.make_payment(
                credit_sale_id=credit_sale_id,
                amount=amount,
                payment_method=payment_method,
                reference_no=reference_no,
                note=note,
                payment_date=payment_date,
            )

        if not auto_allocate:
            return {'success': False, 'error': 'No credit invoice selected'}

        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT id, balance_amount
                FROM credit_sales
                WHERE customer_id = ?
                  AND status NOT IN ('paid', 'refunded')
                  AND COALESCE(balance_amount, 0) > 0
                ORDER BY
                  COALESCE(NULLIF(due_date, ''), NULLIF(sale_date, ''), CAST(created_at AS TEXT)) ASC,
                  id ASC
            """, (customer_id,))
            invoices = cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to load outstanding credit invoices: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

        remaining = amount
        total_allocated = 0.0
        allocations = []

        for invoice_id, balance in invoices:
            if remaining <= 0:
                break
            apply_amount = min(remaining, float(balance or 0))
            if apply_amount <= 0:
                continue
            result = self.make_payment(
                credit_sale_id=invoice_id,
                amount=apply_amount,
                payment_method=payment_method,
                reference_no=reference_no,
                note=note,
                payment_date=payment_date,
            )
            if not result.get('success'):
                return {
                    'success': False,
                    'error': result.get('error', 'Failed to allocate payment'),
                    'total_allocated': total_allocated,
                    'unallocated': remaining,
                    'allocations': allocations,
                }
            remaining -= apply_amount
            total_allocated += apply_amount
            allocations.append({
                'credit_sale_id': invoice_id,
                'amount': apply_amount,
                'new_balance': result.get('new_balance', 0),
            })

        return {
            'success': total_allocated > 0,
            'message': 'Payment recorded successfully' if total_allocated > 0 else 'No outstanding credit invoices',
            'total_allocated': total_allocated,
            'unallocated': max(remaining, 0.0),
            'allocations': allocations,
            'error': None if total_allocated > 0 else 'No outstanding credit invoices',
        }
    
    def get_payments(self, credit_sale_id: int) -> List[Dict]:
        """Get all payments for a credit sale."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, amount, payment_date, payment_method, reference_no, note, created_at
                FROM credit_payments
                WHERE credit_sale_id = ?
                ORDER BY payment_date DESC
            """, (credit_sale_id,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'amount': row[1],
                    'payment_date': row[2],
                    'payment_method': row[3],
                    'reference_no': row[4],
                    'note': row[5],
                    'created_at': row[6]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get payments: {e}")
            return []
        finally:
            conn.close()
    
    # ============================================================
    # ✅ FIXED: REFUND OPERATIONS (no 'refunded_at' column)
    # ============================================================
    
    def refund_credit_sale(self, credit_sale_id: int, reason: str = "Refund", 
                           refund_type: str = 'full') -> Dict:
        """
        Refund a credit sale.
        
        ⚠️ FIX: Removed 'refunded_at' column reference.
        Uses status = 'refunded' to track refund state.
        
        Args:
            credit_sale_id: Credit sale ID
            reason: Reason for refund
            refund_type: 'full' or 'partial' (default: 'full')
            
        Returns:
            Dict with success status
        """
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("BEGIN IMMEDIATE")
            
            # Get credit sale details
            cursor.execute("""
                SELECT id, customer_id, invoice_no, total_amount, paid_amount, 
                       balance_amount, status
                FROM credit_sales
                WHERE id = ?
            """, (credit_sale_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return {'success': False, 'error': 'Credit sale not found'}
            
            credit_id, customer_id, invoice_no, total_amount, paid_amount, balance_amount, status = row
            
            # Check if already refunded
            if status == 'refunded':
                conn.rollback()
                return {'success': False, 'error': 'Credit sale already refunded'}
            
            # ✅ FIX: Remove 'refunded_at' - use status only
            # Update credit sale to refunded status
            cursor.execute("""
                UPDATE credit_sales
                SET status = 'refunded',
                    balance_amount = 0,
                    notes = COALESCE(notes, '') || ?
                WHERE id = ?
            """, (f" [REFUNDED: {reason} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]", credit_sale_id))
            
            outstanding_to_remove = max(float(balance_amount or 0), 0)

            # Remove the unpaid outstanding amount from the customer's balance.
            if outstanding_to_remove > 0:
                cursor.execute("""
                    UPDATE customers
                    SET current_balance = CASE
                            WHEN COALESCE(current_balance, 0) - ? < 0 THEN 0
                            ELSE COALESCE(current_balance, 0) - ?
                        END,
                        credit_balance = CASE
                            WHEN COALESCE(credit_balance, 0) - ? < 0 THEN 0
                            ELSE COALESCE(credit_balance, 0) - ?
                        END
                    WHERE id = ?
                """, (
                    outstanding_to_remove, outstanding_to_remove,
                    outstanding_to_remove, outstanding_to_remove,
                    customer_id,
                ))

            # If there's a paid amount, record refund payment
            if paid_amount > 0:
                # Record refund payment (negative amount)
                cursor.execute("""
                    INSERT INTO credit_payments 
                    (credit_sale_id, customer_id, amount, payment_date, payment_method, note)
                    VALUES (?, ?, ?, CAST(CURRENT_TIMESTAMP AS TEXT), 'refund', ?)
                """, (credit_sale_id, customer_id, -paid_amount, f"Refund: {reason}"))
            
            # Record in credit_adjustments for audit trail
            cursor.execute("""
                INSERT INTO credit_adjustments 
                (customer_id, credit_sale_id, amount, adjustment_type, reason, created_by)
                VALUES (?, ?, ?, 'refund', ?, 'System')
            """, (customer_id, credit_sale_id, -total_amount, reason))
            
            conn.commit()
            
            return {
                'success': True,
                'message': f'Credit sale refunded successfully: {reason}',
                'refunded_amount': total_amount
            }
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to refund credit sale: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    # ============================================================
    # CREDIT SUMMARY
    # ============================================================
    
    def get_customer_credit_summary(self, customer_id: int) -> Dict:
        """Get credit summary for a customer."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            # Get total credit
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_amount), 0) as total_credit,
                    COALESCE(SUM(paid_amount), 0) as total_paid,
                    COALESCE(SUM(balance_amount), 0) as total_balance,
                    COUNT(*) as total_invoices
                FROM credit_sales
                WHERE customer_id = ? AND status != 'refunded'
            """, (customer_id,))
            
            row = cursor.fetchone()
            
            # Get pending count
            cursor.execute("""
                SELECT COUNT(*) 
                FROM credit_sales
                WHERE customer_id = ? AND status IN ('pending', 'partial')
            """, (customer_id,))
            
            pending_count = cursor.fetchone()[0]
            
            # Get overdue count
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT COUNT(*) 
                FROM credit_sales
                WHERE customer_id = ? 
                  AND status IN ('pending', 'partial')
                  AND due_date < ?
            """, (customer_id, today))
            
            overdue_count = cursor.fetchone()[0]
            
            return {
                'total_credit': row[0] or 0,
                'total_paid': row[1] or 0,
                'total_balance': row[2] or 0,
                'total_invoices': row[3] or 0,
                'pending_count': pending_count,
                'overdue_count': overdue_count
            }
            
        except Exception as e:
            logger.error(f"Failed to get customer credit summary: {e}")
            return {
                'total_credit': 0,
                'total_paid': 0,
                'total_balance': 0,
                'total_invoices': 0,
                'pending_count': 0,
                'overdue_count': 0
            }
        finally:
            conn.close()
    
    def get_all_credit_summary(self, status: str = None) -> Dict:
        """Get overall credit summary."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            query = """
                SELECT 
                    COALESCE(SUM(total_amount), 0) as total_credit,
                    COALESCE(SUM(paid_amount), 0) as total_paid,
                    COALESCE(SUM(balance_amount), 0) as total_balance,
                    COUNT(*) as total_invoices
                FROM credit_sales
                WHERE status != 'refunded'
            """
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            return {
                'total_credit': row[0] or 0,
                'total_paid': row[1] or 0,
                'total_balance': row[2] or 0,
                'total_invoices': row[3] or 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get credit summary: {e}")
            return {
                'total_credit': 0,
                'total_paid': 0,
                'total_balance': 0,
                'total_invoices': 0
            }
        finally:
            conn.close()
    
    def get_overdue_credit_sales(self) -> List[Dict]:
        """Get all overdue credit sales."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT 
                    cs.id, cs.invoice_no, cs.customer_id, c.name as customer_name,
                    cs.total_amount, cs.paid_amount, cs.balance_amount,
                    cs.sale_date, cs.due_date, cs.status
                FROM credit_sales cs
                LEFT JOIN customers c ON cs.customer_id = c.id
                WHERE cs.status IN ('pending', 'partial')
                  AND cs.due_date < ?
                ORDER BY cs.due_date ASC
            """, (today,))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'invoice_no': row[1],
                    'customer_id': row[2],
                    'customer_name': row[3],
                    'total_amount': row[4],
                    'paid_amount': row[5],
                    'balance_amount': row[6],
                    'sale_date': row[7],
                    'due_date': row[8],
                    'status': row[9],
                    'days_overdue': (datetime.now() - datetime.strptime(row[8], "%Y-%m-%d")).days
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get overdue credit sales: {e}")
            return []
        finally:
            conn.close()
    
    # ============================================================
    # CREDIT TRANSACTIONS (Unified Audit Trail)
    # ============================================================
    
    def log_transaction(self, customer_id: int, amount: float,
                       transaction_type: str, credit_sale_id: int = None,
                       reference_no: str = None, notes: str = None) -> bool:
        """
        Log a credit transaction for audit trail.
        
        Args:
            customer_id: Customer ID
            credit_sale_id: Optional credit sale ID
            amount: Transaction amount
            transaction_type: 'sale', 'payment', 'refund', 'adjustment'
            reference_no: Optional reference number
            notes: Optional notes
            
        Returns:
            bool: Success status
        """
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO credit_transactions 
                (credit_sale_id, customer_id, amount, transaction_type, reference_no, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (credit_sale_id, customer_id, amount, transaction_type, reference_no, notes))
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to log credit transaction: {e}")
            return False
        finally:
            conn.close()
    
    def get_transactions(self, customer_id: int, limit: int = 50) -> List[Dict]:
        """Get credit transactions for a customer."""
        conn = connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT 
                    id, credit_sale_id, amount, transaction_type, 
                    reference_no, notes, created_at
                FROM credit_transactions
                WHERE customer_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (customer_id, limit))
            
            rows = cursor.fetchall()
            
            return [
                {
                    'id': row[0],
                    'credit_sale_id': row[1],
                    'amount': row[2],
                    'transaction_type': row[3],
                    'reference_no': row[4],
                    'notes': row[5],
                    'created_at': row[6]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Failed to get transactions: {e}")
            return []
        finally:
            if owns_connection:
                conn.close()
