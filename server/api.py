"""FastAPI entrypoint for browser cashier mode."""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from utils.env_loader import load_project_env
from utils.paths import get_product_images_dir

load_project_env()

from server import cashier_service
from server.asyncio_errors import install_windows_disconnect_handler


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ASSETS_DIR = BASE_DIR.parent / "assets"
PRODUCT_IMAGES_DIR = Path(get_product_images_dir())
PRODUCT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="KAY POS Cashier Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/product-images", StaticFiles(directory=str(PRODUCT_IMAGES_DIR)), name="product_images")

_TOKENS: Dict[str, Dict[str, Any]] = {}


async def _start_car_management_service_with_retry(
    attempts: int = 12,
    delay_seconds: float = 5.0,
) -> None:
    """Start the Car service once PostgreSQL is ready during Windows boot."""
    from server.car_management_service import create_configured_car_service

    for attempt in range(1, attempts + 1):
        try:
            service = create_configured_car_service()
            service.start()
            app.state.car_management_service = service
            app.state.car_management_retry_task = None
            if attempt > 1:
                logger.info(f"Car Management service started after retry {attempt}/{attempts}")
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            app.state.car_management_service = None
            if attempt >= attempts:
                logger.error(
                    f"Could not start Car Management service after {attempts} attempts: {exc}"
                )
                app.state.car_management_retry_task = None
                return
            logger.warning(
                f"Car Management service is not ready ({exc}); "
                f"retrying in {delay_seconds:g} seconds ({attempt}/{attempts})"
            )
            await asyncio.sleep(delay_seconds)


@app.on_event("startup")
async def configure_asyncio_error_handling() -> None:
    """Keep expected Windows browser disconnects out of the server console."""
    loop = asyncio.get_running_loop()
    app.state.asyncio_loop = loop
    app.state.previous_asyncio_exception_handler = install_windows_disconnect_handler(loop)
    try:
        from models.database.stock_audit import clamp_all_location_stock_to_master
        fixed = clamp_all_location_stock_to_master("Cashier Server Startup")
        if fixed:
            logger.info(f"Clamped stale location stock for {len(fixed)} product(s)")
    except Exception as exc:
        logger.warning(f"Could not clamp stale location stock on cashier startup: {exc}")
    app.state.car_management_service = None
    app.state.car_management_retry_task = None
    from server.car_management_service import car_server_enabled
    if car_server_enabled():
        app.state.car_management_retry_task = asyncio.create_task(
            _start_car_management_service_with_retry()
        )


@app.on_event("shutdown")
async def restore_asyncio_error_handling() -> None:
    """Restore the event loop handler when the cashier server stops."""
    retry_task = getattr(app.state, "car_management_retry_task", None)
    if retry_task is not None and not retry_task.done():
        retry_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await retry_task
    car_service = getattr(app.state, "car_management_service", None)
    if car_service is not None:
        car_service.stop()
    loop = getattr(app.state, "asyncio_loop", None)
    if loop is not None and not loop.is_closed():
        loop.set_exception_handler(
            getattr(app.state, "previous_asyncio_exception_handler", None)
        )


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/car/request")
def car_management_https_request(
    payload: Dict[str, Any],
    x_car_api_key: Optional[str] = Header(default=None),
):
    """Authenticated HTTPS transport for remote Car Management clients."""
    configured_key = os.getenv("ZAY_CAR_API_KEY", "").strip()
    if not configured_key:
        raise HTTPException(status_code=503, detail="Cloud Car Management is not configured.")
    if not x_car_api_key or not secrets.compare_digest(x_car_api_key, configured_key):
        raise HTTPException(status_code=401, detail="Invalid Car Management API key.")
    from server.car_management_service import CarRequestHandler

    result = CarRequestHandler().process(payload)
    if result.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail=result.get("message") or "Car request failed.")
    return result


class CartItem(BaseModel):
    product_id: int = Field(..., gt=0)
    qty: int = Field(..., gt=0)
    manual_price: Optional[float] = None


class SaleRequest(BaseModel):
    items: List[CartItem]
    payment: float = 0
    payment_type: str = "Cash"
    sale_mode: str = "Cash"
    discount_amount: float = 0
    points_used: int = 0
    customer_id: Optional[int] = None


class ExpenseRequest(BaseModel):
    category: str
    description: str = ""
    amount: float = Field(..., gt=0)
    expense_date: str = ""
    payment_method: str = "Cash"
    reference_no: str = ""
    notes: str = ""


def current_user(authorization: str = Header(default="")) -> Dict[str, Any]:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or token not in _TOKENS:
        raise HTTPException(status_code=401, detail="Login required")
    return _TOKENS[token]


@app.get("/", response_class=HTMLResponse)
def dashboard_home():
    return FileResponse(STATIC_DIR / "dashboard.html", headers={"Cache-Control": "no-store"})


@app.get("/cashier", response_class=HTMLResponse)
def cashier_home():
    return FileResponse(STATIC_DIR / "cashier.html", headers={"Cache-Control": "no-store"})


@app.get("/receipts", response_class=HTMLResponse)
def receipts_home():
    return FileResponse(STATIC_DIR / "receipts.html", headers={"Cache-Control": "no-store"})


@app.get("/mobile/products", response_class=HTMLResponse)
def mobile_products_home():
    return FileResponse(STATIC_DIR / "mobile_products.html", headers={"Cache-Control": "no-store"})


@app.get("/health")
def health():
    return {"ok": True, "service": "kay-pos-cashier"}


@app.post("/api/login")
def login(payload: LoginRequest):
    user = cashier_service.verify_user(payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/password or inactive user")
    token = secrets.token_urlsafe(32)
    _TOKENS[token] = user
    return {"token": token, "user": user}


@app.get("/api/me")
def me(user: Dict[str, Any] = Depends(current_user)):
    return {"user": user}


@app.get("/api/dashboard/summary")
def dashboard_summary(
    from_date: str = Query(default=""),
    to_date: str = Query(default=""),
    trend_days: int = Query(default=0, ge=0, le=31),
    _: Dict[str, Any] = Depends(current_user),
):
    try:
        return cashier_service.get_dashboard_summary(from_date, to_date, trend_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/categories")
def categories(_: Dict[str, Any] = Depends(current_user)):
    return {"categories": cashier_service.list_categories()}


@app.get("/api/products")
def products(
    q: str = Query(default=""),
    category: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: Dict[str, Any] = Depends(current_user),
):
    return {"products": cashier_service.list_products(q.strip(), category.strip(), limit, offset)}


@app.get("/api/products/barcode/{barcode}")
def product_by_barcode(barcode: str, _: Dict[str, Any] = Depends(current_user)):
    return {"product": cashier_service.barcode_exists(barcode.strip())}


@app.post("/api/mobile/products")
async def create_mobile_product(
    name: str = Form(...),
    barcode: str = Form(default=""),
    sku: str = Form(default=""),
    category: str = Form(default=""),
    price: float = Form(default=0),
    cost: float = Form(default=0),
    stock: int = Form(default=0),
    low_stock: int = Form(default=0),
    unit: str = Form(default=""),
    location: str = Form(default="Mobile Entry"),
    image: Optional[UploadFile] = File(default=None),
    user: Dict[str, Any] = Depends(current_user),
):
    try:
        image_bytes = await image.read() if image else b""
        product = cashier_service.create_mobile_product(
            name=name,
            barcode=barcode,
            sku=sku,
            category=category,
            price=price,
            cost=cost,
            stock=stock,
            low_stock=low_stock,
            unit=unit,
            location=location,
            image_bytes=image_bytes,
            image_filename=image.filename if image else "",
            image_content_type=image.content_type if image else "",
            created_by=user.get("username", "Mobile"),
        )
        return {"product": product}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/products/{product_id}/image")
def product_image(product_id: int):
    image_path = cashier_service.get_product_image_path(product_id)
    if image_path:
        return FileResponse(image_path)

    image_blob = cashier_service.get_product_image_blob(product_id)
    if image_blob:
        return Response(
            content=image_blob["data"],
            media_type=image_blob["mime"],
            headers={"Content-Disposition": f'inline; filename="{image_blob["filename"]}"'},
        )

    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/customers")
def customers(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    _: Dict[str, Any] = Depends(current_user),
):
    return {"customers": cashier_service.list_customers(q.strip(), limit)}


@app.get("/api/payment-types")
def payment_types(_: Dict[str, Any] = Depends(current_user)):
    return {"payment_types": cashier_service.list_payment_types()}


@app.get("/api/settings/cashier")
def cashier_settings(_: Dict[str, Any] = Depends(current_user)):
    return {"settings": cashier_service.get_cashier_settings()}


@app.get("/api/expenses/categories")
def expense_categories(_: Dict[str, Any] = Depends(current_user)):
    return {"categories": cashier_service.list_expense_categories()}


@app.post("/api/expenses")
def add_expense(payload: ExpenseRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        expense = cashier_service.add_expense(
            category=payload.category,
            description=payload.description,
            amount=payload.amount,
            expense_date=payload.expense_date,
            payment_method=payload.payment_method,
            reference_no=payload.reference_no,
            notes=payload.notes,
            created_by=user.get("username", "Browser Cashier"),
        )
        return {"expense": expense}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/cashdrawer/open")
def open_cashdrawer(_: Dict[str, Any] = Depends(current_user)):
    try:
        return cashier_service.open_cash_drawer()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sales")
def create_sale(payload: SaleRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        receipt = cashier_service.create_sale(
            items=[item.dict() for item in payload.items],
            payment=payload.payment,
            payment_type=payload.payment_type,
            sale_mode=payload.sale_mode,
            discount_amount=payload.discount_amount,
            points_used=payload.points_used,
            customer_id=payload.customer_id,
            created_by=user.get("username", "Browser Cashier"),
        )
        return {"receipt": receipt}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Browser cashier checkout failed")
        raise HTTPException(status_code=500, detail=f"Checkout failed: {exc}") from exc


@app.get("/api/receipts/overview")
def receipts_overview(
    from_date: str = Query(...),
    to_date: str = Query(...),
    tab: str = Query(default="receipts"),
    q: str = Query(default=""),
    payment_type: str = Query(default=""),
    customer_type: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Dict[str, Any] = Depends(current_user),
):
    try:
        return cashier_service.get_receipts_overview(
            from_date=from_date,
            to_date=to_date,
            tab=tab,
            search=q.strip(),
            payment_type=payment_type.strip(),
            customer_type=customer_type.strip().lower(),
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/receipts/{sale_id}")
def receipt(sale_id: int, _: Dict[str, Any] = Depends(current_user)):
    try:
        return {"receipt": cashier_service.get_receipt(sale_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/receipts")
def receipts(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Dict[str, Any] = Depends(current_user),
):
    return {"receipts": cashier_service.list_receipts(q.strip(), limit, offset)}


@app.get("/api/settings/receipt")
def receipt_settings(_: Dict[str, Any] = Depends(current_user)):
    return {"settings": cashier_service.get_receipt_settings()}
