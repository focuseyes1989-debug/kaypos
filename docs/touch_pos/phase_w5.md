# KAY POS Touch - Phase W5

Date: 2026-09-05
Status: Cash checkout implemented

W5 connects the Touch POS cart to a cash payment workflow. Staff can enter cash received, use quick cash buttons, see change due, complete a cash sale, and view a compact receipt confirmation after the server saves the sale.

## Checkout behavior

- `/api/touch-pos/sales` uses the same staff permission gate as the Touch POS session and catalog endpoints.
- The endpoint delegates to the existing POS Lite sale service, so stock deduction, invoice creation, receipt data, and server-side payment validation stay in one existing transaction path.
- The browser blocks checkout when the cart is empty or cash received is lower than the total.
- Submitted items include product id, optional variant id, quantity, and manual service price.
- After a successful cash sale, the cart draft is cleared, catalog stock is refreshed, and a receipt summary is shown.
- Failed checkout keeps the cart in place so staff can retry after correcting payment or refreshing stock.

Hold sale continues in [Phase W6](phase_w6.md). Customer credit sales, customer points, receipt printing, and drawer opening remain for later phases.
