# Inventory batch and expiry compatibility

Audit: 2026-09-08. Applies to this repository's desktop KAY POS, Lite and Touch clients.

## Contract for non-variant stock

- Batch identifier: `product_locations.batch_no`, independent of expiry. Blank input generates a timestamp identifier including microseconds. A user-supplied batch number is preserved.
- Expiry: `product_locations.expire_date`, calendar date `YYYY-MM-DD`. No expiry is an empty string; readers also accept legacy NULL.
- Batch identity includes product, location, batch number and expiry date. Receiving the same identity increases its quantity; different expiries must remain separate.
- New stock-in forms default to one calendar year from today, with an editable date and No expiry option. February 29 clamps to February 28 in the following non-leap year.
- Lite and Touch send `expire_date` to `/api/stock/adjust`. Existing clients that omit it continue to mean No expiry; the server must not silently invent an expiry for old callers.
- Desktop writes the same batch fields directly. Its expiry selector was previously created but absent from the layout; it is now visible with No expiry support.
- Desktop expiry reporting reads location batches. The legacy `products.expire_date` field is not a reliable multi-batch expiry source: desktop overwrites it on receipt, while the API tracks expiry on each location batch.

## Limits found by the audit

- Variant batches are NOT interchangeable yet. Desktop writes variant stock plus product-level location batches without a variant key. Lite/Touch update variant stock without per-variant batches and only offer No expiry. Supporting variant expiry safely requires a variant-aware batch schema and coordinated receiving, sale allocation, refund, transfer and reversal changes across all clients. Do not infer that an expiry on a product-level batch belongs to a specific variant.
- Expiry ordering is not an expired-sale prohibition. The server allocates dated batches first, then undated batches, but does not reject an expired batch solely because of its date. A common sale policy needs a separate explicit decision.
- Older desktop/Lite executables do not gain these UI changes from a server-only update. Rebuild/update those clients as well as deploying the server. Touch reloads the web client.
- Existing data is not rewritten by these changes. No-expiry history remains undated; unknown historical dates are not inferred.

## Verification

- `tests/test_lite_expiry_contract.py`: dated and undated API payloads, backwards-compatible omitted date.
- `tests/test_cashier_service_products.py`: dated/undated batch separation, merging identical batches, invalid date rejection and stock/cost/history persistence in a temporary SQLite database.
- `tests/test_touch_inventory.cjs`: next-year default, No expiry toggle and stock-in payload.
- Python compilation checks cover the modified desktop and Lite form code. Full installed desktop/Lite end-to-end UI testing is still required before claiming complete release compatibility.
