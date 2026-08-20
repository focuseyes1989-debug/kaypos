"""Cloud entrypoint for KAY POS hybrid mode.

This module is intended for hosted FastAPI deployments. It switches the app to
PostgreSQL before importing the normal API module, then verifies/creates the
PostgreSQL schema on startup.
"""

from __future__ import annotations

import os

from loguru import logger

from utils.env_loader import load_project_env


load_project_env()
os.environ.setdefault("ZAY_POS_DB_BACKEND", "postgres")
# Hosted platforms expose HTTPS, not the LAN-only raw TCP listener.
os.environ.setdefault("ZAY_CAR_SERVER_ENABLED", "0")

if os.getenv("DATABASE_URL") and not os.getenv("ZAY_POS_DATABASE_URL"):
    os.environ["ZAY_POS_DATABASE_URL"] = os.environ["DATABASE_URL"]

from models.database import safe_initialize_database  # noqa: E402


if os.getenv("ZAY_POS_AUTO_INIT_DB", "1").strip().lower() in {"1", "true", "yes", "on"}:
    if not safe_initialize_database():
        raise RuntimeError("Could not initialize PostgreSQL schema for cloud POS.")
    logger.info("Cloud PostgreSQL schema is ready.")

from server.api import app  # noqa: E402
