# KAY POS Touch - Phase W6

Date: 2026-09-05
Status: Hold sale implemented

W6 adds a local hold-sale workflow for the Touch POS cash register. Staff can hold the current cart, clear the active sale area, and restore the held sale later in the same browser tab.

## Hold behavior

- Held sale data is stored in `sessionStorage` with the cart items, total, and hold timestamp.
- Holding a sale does not call the sale API and does not mutate stock, invoices, receipts, or payments.
- Restore is disabled until a held sale exists.
- Restore is blocked while the current cart has items, so staff do not accidentally merge two sale drafts.
- Restoring a held sale removes it from the hold slot and returns it to the active cart.
- Sign out, session expiry, or account change clears both the active cart and held sale data.

Receipt printing continues in [Phase W7](phase_w7.md). Only one held sale is supported in W6. Multiple held sales, customer labels, and shared cross-device hold queues remain for later phases.
