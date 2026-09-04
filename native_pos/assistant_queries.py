"""Pure assistant report shortcuts shared by UI and server."""
REPORT_CHOICES = (
    ('Sales overview', 'summary', 'overview'), ('Daily sales', 'summary', 'daily'),
    ('Hourly sales', 'summary', 'hourly'), ('Top products', 'summary', 'items'),
    ('Wholesale items', 'summary', 'wholesale'), ('Category sales', 'summary', 'categories'),
    ('Parent category sales', 'summary', 'parents'), ('Category group sales', 'summary', 'groups'),
    ('Payment types', 'summary', 'payments'), ('Refunded items', 'summary', 'returns'),
    ('Financial summary', 'reports', 'financial'), ('Monthly profit', 'reports', 'monthly'),
    ('Sales invoices', 'reports', 'invoices'), ('Expenses', 'reports', 'expenses'),
    ('Credit collections', 'reports', 'credit'), ('Inventory valuation', 'reports', 'inventory'),
    ('Stock movements', 'reports', 'movements'),
)
