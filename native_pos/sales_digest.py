"""Deterministic sales narrative from the authorized report snapshot."""
from datetime import date, timedelta
import re


def digest_period(query, today=None):
    today = today or date.today()
    match = re.fullmatch(r'digest (daily|weekly|monthly)', query.strip(), re.I)
    if match:
        kind = match[1].lower()
        start = today - timedelta(days=today.weekday()) if kind == 'weekly' else today.replace(day=1) if kind == 'monthly' else today
        return start.isoformat(), today.isoformat()
    match = re.fullmatch(r'digest (\d{4}-\d{2}-\d{2}) (\d{4}-\d{2}-\d{2})', query.strip(), re.I)
    if match: return match[1], match[2]
    if query.strip().lower().startswith('digest'):
        raise ValueError('Use digest daily, digest weekly, digest monthly, or digest YYYY-MM-DD YYYY-MM-DD.')
    return None


def digest_message(report):
    metrics = report['metrics']; previous = report['previous_period']; currency = report['currency']
    rows = next(table['rows'] for table in report['tables'] if table.get('key') == 'comparison')
    invoice = next(row for row in rows if row['label'] == 'Invoice Total')
    change = float(invoice['change'])
    percent = 'percentage unavailable because the previous total was zero' if invoice['percent'] is None else f"{float(invoice['percent']):+.2f}%"
    lines = [f"Sales digest · {report['start']} to {report['end']}",
             f"As of {report['as_of']}; this is an on-demand report, not a finalized closing record.",
             f"Completed invoices: {int(metrics['transactions']):,}; invoice total: {float(metrics['invoice_total']):,.2f} {currency}.",
             f"Average completed invoice: {float(metrics['average_invoice']):,.2f} {currency}.",
             f"Compared with {previous['start']} to {previous['end']}: {change:+,.2f} {currency} ({percent}).",
             f"Refunded invoice total: {float(metrics['refunds']):,.2f} {currency}. Refunds are shown separately; invoice totals are not cash collections."]
    if not metrics['transactions']: lines.append('No completed invoices were found in the selected period.')
    lines.extend(report.get('notes', []))
    lines.append('Source: Sales Summary overview. Use the tables below to inspect comparison and daily totals.')
    return '\n\n'.join(lines)
