"""FastAPI entrypoint for browser cashier mode."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import cashier_service


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="ZAY POS Cashier Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_TOKENS: Dict[str, Dict[str, Any]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


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
def cashier_home():
    return FileResponse(STATIC_DIR / "cashier.html")


@app.get("/health")
def health():
    return {"ok": True, "service": "zay-pos-cashier"}


@app.post("/api/login")
def login(payload: LoginRequest):
    user = cashier_service.verify_user(payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/password or inactive user")
    token = secrets.token_urlsafe(32)
    _TOKENS[token] = user
    return {"token": token, "user": user}


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
