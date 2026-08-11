# Restaurant Database Migration Plan

## Goal

Restaurant Mode should keep working with the current SQLite database while new code is written in a way that can move to PostgreSQL later.

## Phase 1 - SQLite-safe service boundary

- Keep Restaurant Mode data access inside service modules such as `utils/restaurant_service.py`.
- Use `utils/db_compat.py` for new schema helpers, timestamp SQL, primary-key SQL, and future backend-specific SQL.
- Avoid putting restaurant order SQL directly inside UI widgets.

## Phase 2 - Restaurant data model cleanup

- Add explicit kitchen ticket tables instead of storing only cart JSON. This starts with `restaurant_kitchen_tickets` and `restaurant_kitchen_ticket_items`.
- Add order item and order modifier rows for reporting and kitchen printing. This starts with `restaurant_order_items` and `restaurant_order_modifiers`.
- Keep cart JSON as a short-term snapshot only.

## Phase 3 - Backend configuration

- Add a database backend setting, for example `ZAY_POS_DB_BACKEND=sqlite` or `postgres`.
- Keep SQLite as the default for single-device shops.
- Add PostgreSQL connection settings only after service-layer tests are in place.

## Phase 4 - PostgreSQL-ready schema

- Convert SQLite-only migration SQL into backend-aware migration helpers.
- Replace `lastrowid` usage in shared services with a helper that supports PostgreSQL `RETURNING id`.
- Add indexes for open orders, kitchen status, table status, and sales settlement.

## Phase 5 - Multi-device restaurant workflow

- Add an API/server layer for cashier, waiter, and kitchen displays.
- Use PostgreSQL when multiple devices need to update orders at the same time.
- Add kitchen ticket status flow: draft, sent, preparing, ready, served, settled.
