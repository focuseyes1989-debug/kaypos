# Inventory expiry compatibility

## Shared contract

The source clients use `YYYY-MM-DD` for a known expiry and an empty string for explicitly selected No expiry. Forms start at No expiry; Enter expiry date requires the known date. Batch identifiers and expiry are independent.

Standard products continue to use `product_locations`. Variants use `variant_stock_batches`, keyed by product, variant, location, batch and expiry. `variant_batch_changes` stores exact stock movement allocations for reversals. Both tables are created idempotently by desktop initialization or first use by the shared service. Original product/variant balances are retained.

Desktop receiving, sale deductions and refunds share the batch ledger used by the server for Lite and Touch. Desktop variant stock-out, count correction and transfer prompt for the variant and route through the shared service. Transfers preserve expiry. A reverse transfer, not movement reversal, undoes a transfer.

## Existing stock and compatibility boundaries

- Existing product-level batches are preserved and never guessed into variants. Missing variant balances become an unknown `LEGACY-OPENING` at `Legacy / unassigned` on first mutation. Unknown is distinct from No expiry.
- If an old client reduces stock below the tracked batch balance, operations fail with a review message rather than deducting an arbitrary batch. All stock-writing clients must be updated together.
- Historical movements without allocations cannot be reversed once batch tracking starts; use a reviewed compensating adjustment. New receiving/out/count movements record exact batch allocations for reversal.
- Desktop Inventory > Expiry > Variant batches / expiry is a separate read-only report, including virtual unknown opening balances. Stock-in forms show known variant batches. The standard product expiry report still describes product-level batches.
- Expiry ordering does not itself forbid selling expired goods. A uniform expiry-sale blocking policy is outside this change.
- Cloud sync transport/schema changes are not included. Replication must include both new tables before it can be treated as a complete copy of variant stock.
- Old clients omitting expiry still mean No expiry. The legacy `products.expire_date` is not a multi-batch source of truth.

## Coordinated rollout

Stop the clients and server, back up the complete database, update all source checkouts to the same commit, restart the server and desktop/Lite clients, then refresh Touch. Database recreation is not needed. Never infer historical expiry dates from the installation date.

## Verification

Temporary SQLite tests cover variant identity, date separation, earliest-expiry allocation, rollback, unknown opening stock, desktop sale followed by API refund, transfer, count corrections, and reversal. Lite API payload and Touch UI tests cover manual expiry and No expiry. Full multi-PC production acceptance testing is still required; tests do not modify the production database.
