"""Field definitions shared by stock Qt forms and server validation (no Qt imports)."""

# Each field is (database name, label, input kind, default).
EMPLOYEE_FIELDS = (
    ('employee_no', 'Employee number', 'text', ''), ('user_id', 'Login account', 'user', None),
    ('full_name', 'Full name', 'text', ''), ('phone', 'Phone', 'text', ''),
    ('hire_date', 'Hire date', 'date', ''), ('employment_status', 'Status', ('Active', 'Inactive', 'Resigned'), 'Active'),
    ('position', 'Position', 'text', ''), ('department', 'Department', 'text', ''),
    ('branch', 'Branch', 'text', ''), ('date_of_birth', 'Date of birth (YYYY-MM-DD, optional)', 'text', ''),
    ('national_id', 'National ID', 'text', ''), ('address', 'Address', 'text', ''),
    ('emergency_contact_name', 'Emergency contact', 'text', ''), ('emergency_contact_phone', 'Emergency phone', 'text', ''),
    ('notes', 'Notes', 'memo', ''),
)
PAY_FIELDS = tuple((key, key.replace('_', ' ').title(), 'money', 0) for key in
                  ('basic_salary', 'allowance', 'overtime_amount', 'bonus', 'late_deduction',
                   'absence_deduction', 'advance_deduction', 'other_deduction'))

EMPLOYEE_SECTIONS = {
    'employees': ('Employees', 'employees', 'employees', 'manage_employees', EMPLOYEE_FIELDS),
    'shifts': ('Shifts', 'shifts', 'shifts', 'manage_shifts', (
        ('name', 'Name', 'text', ''), ('start_time', 'Start (HH:MM)', 'text', '08:00'),
        ('end_time', 'End (HH:MM)', 'text', '17:00'), ('break_minutes', 'Break minutes', 'int', 0),
        ('is_overnight', 'Overnight', 'bool', False))),
    'assignments': ('Shift assignments', 'shifts', 'employee_shifts', 'manage_shifts', (
        ('employee_id', 'Employee', 'employee', None), ('shift_id', 'Shift', 'shift', None),
        ('effective_from', 'Effective from', 'date', ''), ('effective_to', 'Effective to (optional YYYY-MM-DD)', 'text', ''),
        ('weekly_off_days', 'Weekly off days (0=Mon … 6=Sun)', 'text', ''))),
    'attendance': ('Attendance', 'attendance', 'attendance', 'manage_attendance', (
        ('employee_id', 'Employee', 'employee', None), ('attendance_date', 'Date', 'date', ''),
        ('check_in', 'Check in (HH:MM)', 'text', ''), ('check_out', 'Check out (HH:MM)', 'text', ''),
        ('status', 'Status', ('Present', 'Late', 'Incomplete', 'Leave', 'Absent'), 'Present'),
        ('notes', 'Notes', 'text', ''), ('correction_reason', 'Correction reason (required)', 'text', ''))),
    'leave': ('Leave', 'leave', 'employee_leave', 'manage_leave', (
        ('employee_id', 'Employee', 'employee', None), ('leave_type', 'Leave type', 'text', 'Annual'),
        ('start_date', 'Start', 'date', ''), ('end_date', 'End', 'date', ''),
        ('days', 'Days', 'money', 1), ('reason', 'Reason', 'memo', ''))),
    'payroll': ('Payroll', 'payroll', 'payrolls', 'manage_payroll', (
        ('employee_id', 'Employee', 'employee', None), ('period_month', 'Period (YYYY-MM)', 'text', ''),
        *PAY_FIELDS, ('notes', 'Notes', 'memo', ''))),
    'documents': ('Documents', 'employee_documents', 'employee_documents', 'manage_employees', (
        ('employee_id', 'Employee', 'employee', None), ('document_type', 'Document type', 'text', ''),
        ('document_no', 'Document number', 'text', ''), ('file_path', 'Document reference / server path', 'text', ''),
        ('issued_date', 'Issued (optional YYYY-MM-DD)', 'text', ''), ('expiry_date', 'Expiry (optional YYYY-MM-DD)', 'text', ''),
        ('notes', 'Notes', 'memo', ''))),
    'advances': ('Salary advances', 'employee_finance', 'salary_advances', 'manage_employee_finance', (
        ('employee_id', 'Employee', 'employee', None), ('advance_date', 'Date', 'date', ''),
        ('amount', 'Amount', 'money', 0), ('notes', 'Notes', 'memo', ''))),
    'commission': ('Commission rules', 'employee_finance', 'commission_rules', 'manage_employee_finance', (
        ('employee_id', 'Employee', 'employee', None), ('rate_percent', 'Rate %', 'money', 0),
        ('target_amount', 'Sales target', 'money', 0))),
    'cash': ('Cash sessions', 'cash_sessions', 'cash_sessions', 'manage_cash_sessions', (
        ('employee_id', 'Employee', 'employee', None), ('opening_cash', 'Opening cash', 'money', 0),
        ('notes', 'Notes', 'memo', ''))),
    'performance': ('Performance', 'employee_performance', '', '', ()),
}

SETTINGS = {
    'general': (
        ('tax_enabled', 'Tax enabled', 'bool', False), ('tax_rate', 'Tax %', 'money', 0),
        ('discount_enabled', 'Automatic discount', 'bool', False),
        ('discount_type', 'Discount type', ('percentage', 'fixed'), 'percentage'),
        ('discount_value', 'Discount value', 'money', 0),
        ('loyalty_points_per_dollar', 'Loyalty points per currency unit', 'money', 1),
        ('loyalty_min_points_for_reward', 'Minimum reward points', 'int', 100),
        ('loyalty_reward_discount', 'Reward discount', 'money', 0),
        ('points_expiry_months', 'Points expiry months', 'int', 12),
        ('points_dollar_value', 'Value per point', 'money', 1)),
    'receipt': tuple((key, label, kind, '') for key, label, kind in (
        ('shop_name', 'Shop name', 'text'), ('shop_phone', 'Phone', 'text'),
        ('shop_address', 'Address', 'memo'), ('receipt_header', 'Header', 'memo'),
        ('receipt_footer', 'Footer', 'memo'), ('shop_footer_message', 'Thank-you message', 'text'),
        ('shop_qr_name', 'QR payment name', 'text'))),
    'regional': (('currency', 'Currency name', 'text', 'Kyats (Ks)'),
                 ('currency_symbol', 'Currency symbol', 'text', 'Ks'),
                 ('language', 'Original app language', ('en', 'my'), 'en')),
    'performance': (('performance_low_end_mode', 'Low-end mode', 'bool', False),
                    ('performance_product_page_size', 'Product page size', 'int', 60),
                    ('performance_search_debounce_ms', 'Search debounce (ms)', 'int', 300),
                    ('performance_thumbnail_quality', 'Thumbnail quality', ('low', 'normal', 'high'), 'normal'),
                    ('performance_customer_display_youtube_enabled', 'Customer display YouTube', 'bool', False)),
    'youtube': (('customer_display_youtube_url', 'Customer display YouTube URL', 'text', ''),),
}
