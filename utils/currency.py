# utils/currency.py

from models.database import connect_db

def get_currency_symbol():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='currency'")
    row = cursor.fetchone()
    conn.close()
    currency = row[0] if row else "Kyats (Ks)"
    if currency == "Dollar ($)":
        return "$"
    elif currency == "Baht (B)":
        return "B"
    else:
        return "Ks"

def format_money(value, symbol=None):
    """
    Return formatted money string with space between symbol and value.
    
    Examples:
        format_money(1000, "Ks") -> "Ks 1,000"
        format_money(1500.50, "$") -> "$ 1,500.50"
        format_money(0, "Ks") -> "Ks 0"
    """
    if symbol is None:
        symbol = get_currency_symbol()
    
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0
    
    # Round to 2 decimal places
    amount = round(amount, 2)
    
    # Format with thousand separators
    if amount == int(amount):
        # No decimal places if it's a whole number
        formatted = f"{int(amount):,}"
    else:
        # Show 2 decimal places
        formatted = f"{amount:,.2f}"
    
    # Return with space between symbol and value
    return f"{symbol} {formatted}"