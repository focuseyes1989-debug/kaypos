from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from models.database import connect_db
from utils.currency import format_money, get_currency_symbol
from datetime import datetime, timedelta
from loguru import logger


class ExpenseNotificationChecker(QObject):
    alert_triggered = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_budgets)
        self.start_checking()

    def start_checking(self):
        """Start periodic checking for budget alerts"""
        # Check every hour
        self.timer.start(3600000)  # 1 hour in milliseconds
        # Run first check immediately
        QTimer.singleShot(5000, self.check_budgets)

    def check_budgets(self):
        """Check all budgets and create alerts if thresholds are exceeded"""
        conn = connect_db()
        cursor = conn.cursor()

        # Get notification settings
        cursor.execute("""
            SELECT enable_notifications, warning_threshold, check_frequency, last_checked
            FROM expense_notification_settings LIMIT 1
        """)
        settings = cursor.fetchone()

        if not settings or settings[0] != 1:
            conn.close()
            return

        enable_notifications, warning_threshold, check_frequency, last_checked = settings
        symbol = get_currency_symbol()

        # Check based on frequency
        should_check = False
        now = datetime.now()

        last_checked_dt = self._parse_last_checked(last_checked)

        if check_frequency == 'daily':
            if not last_checked_dt or (now - last_checked_dt).days >= 1:
                should_check = True
        elif check_frequency == 'weekly':
            if not last_checked_dt or (now - last_checked_dt).days >= 7:
                should_check = True
        elif check_frequency == 'monthly':
            if not last_checked_dt or (now - last_checked_dt).days >= 30:
                should_check = True

        if not should_check:
            conn.close()
            return

        # Update last checked time
        cursor.execute("""
            UPDATE expense_notification_settings 
            SET last_checked = ? 
            WHERE id = (SELECT id FROM expense_notification_settings LIMIT 1)
        """, (now.isoformat(),))
        conn.commit()

        # Get current month and year
        current_month = now.month
        current_year = now.year

        # Get all budgets for current month
        cursor.execute("""
            SELECT eb.category, eb.budget_amount, COALESCE(SUM(e.amount), 0) as actual
            FROM expense_budgets eb
            LEFT JOIN expenses e ON e.category = eb.category 
                AND strftime('%Y-%m', e.expense_date) = ?
            WHERE eb.month = ? AND eb.year = ?
            GROUP BY eb.category, eb.budget_amount
        """, (f"{current_year}-{current_month:02d}", current_month, current_year))
        
        budgets = cursor.fetchall()

        alerts_created = 0

        for category, budget, actual in budgets:
            if budget <= 0:
                continue

            used_percent = (actual / budget) * 100
            
            # Check if threshold is reached
            if used_percent >= warning_threshold:
                # Check if alert already exists for this category this month
                cursor.execute("""
                    SELECT id FROM expense_alerts_log 
                    WHERE category = ? AND month = ? AND year = ? AND alert_type = 'threshold'
                """, (category, current_month, current_year))
                existing = cursor.fetchone()

                if not existing:
                    alert_type = "exceeded" if used_percent >= 100 else "warning"
                    
                    if used_percent >= 100:
                        message = f"⚠️ Budget exceeded! {category}: {format_money(actual, symbol)} / {format_money(budget, symbol)} ({used_percent:.1f}%)"
                    else:
                        message = f"⚠️ Budget warning! {category}: {format_money(actual, symbol)} / {format_money(budget, symbol)} ({used_percent:.1f}%)"
                    
                    cursor.execute("""
                        INSERT INTO expense_alerts_log 
                        (category, month, year, budget_amount, actual_amount, used_percentage, alert_type, message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (category, current_month, current_year, budget, actual, used_percent, alert_type, message))
                    alerts_created += 1
                    
                    # Emit signal for in-app notification
                    self.alert_triggered.emit({
                        'category': category,
                        'budget': budget,
                        'actual': actual,
                        'percentage': used_percent,
                        'message': message
                    })

        if alerts_created > 0:
            logger.info(f"Created {alerts_created} budget alerts for {current_month}/{current_year}")
            conn.commit()

        conn.close()
        return alerts_created

    def _parse_last_checked(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=None)
        except ValueError:
            return None

    def get_unread_alerts_count(self):
        """Get count of unread alerts"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM expense_alerts_log WHERE is_read = 0")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def mark_alerts_as_read(self):
        """Mark all alerts as read"""
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE expense_alerts_log SET is_read = 1")
        conn.commit()
        conn.close()
