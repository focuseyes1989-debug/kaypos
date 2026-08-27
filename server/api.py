"""FastAPI entrypoint for browser cashier mode."""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")
app.mount("/product-images", StaticFiles(directory=str(PRODUCT_IMAGES_DIR)), name="product_images")

_TOKENS: Dict[str, Dict[str, Any]] = {}
_CAR_PRINT_RATE: Dict[str, List[float]] = {}
_CAR_SEARCH_RATE: Dict[str, List[float]] = {}
_CAR_SEARCH_GRANTS: Dict[str, Dict[str, Any]] = {}


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
        from server.printer_service import PrinterRegistry

        PrinterRegistry().ensure_schema()
    except Exception as exc:
        logger.warning(f"Could not initialize Printer Server registry: {exc}")
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


class LiteSettingsRequest(BaseModel):
    settings: Dict[str, Any] = Field(default_factory=dict)


class PaymentTypeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class CategoryManageRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    parent_id: Optional[int] = Field(default=None, gt=0)
    sort_order: int = Field(default=0, ge=0, le=999999)
    status: str = Field(default="active", max_length=20)


class LiteUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(default="", max_length=256)
    full_name: str = Field(default="", max_length=160)
    role: str = Field(default="Cashier", max_length=80)
    active: bool = True


class CarPrintRequest(BaseModel):
    token: str = Field(..., min_length=32, max_length=128)
    request_key: str = Field(..., min_length=16, max_length=128)
    copies: int = Field(default=1, ge=1, le=99)
    printer_name: str = Field(default="", max_length=255)


class CarSearchPrintRequest(BaseModel):
    grant: str = Field(..., min_length=32, max_length=128)
    request_key: str = Field(..., min_length=16, max_length=128)
    copies: int = Field(default=1, ge=1, le=99)
    printer_name: str = Field(default="", max_length=255)


class PrinterInfoPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    is_default: bool = False


class PrinterAgentHeartbeat(BaseModel):
    agent_id: str = Field(..., min_length=8, max_length=128)
    computer_name: str = Field(..., min_length=1, max_length=120)
    ip_address: str = Field(default="", max_length=64)
    platform: str = Field(default="Windows", max_length=80)
    agent_version: str = Field(default="1.0", max_length=40)
    printers: List[PrinterInfoPayload] = Field(default_factory=list, max_length=100)


class PrinterAgentEnrollment(BaseModel):
    agent_id: str = Field(..., min_length=8, max_length=128)
    computer_name: str = Field(..., min_length=1, max_length=120)


class PrinterAgentPermissions(BaseModel):
    enabled: bool = True
    allowed_job_types: List[str] = Field(default_factory=list, max_length=10)


class NetworkPrinterPermissions(BaseModel):
    printer_name: str = Field(..., min_length=1, max_length=255)
    enabled: bool = True


class NetworkPrintJobRequest(BaseModel):
    request_key: str = Field(..., min_length=8, max_length=128)
    target_agent_id: str = Field(..., min_length=8, max_length=128)
    printer_name: str = Field(..., min_length=1, max_length=255)
    job_type: str = Field(default="test_page", max_length=40)
    payload: Dict[str, Any] = Field(default_factory=dict)
    copies: int = Field(default=1, ge=1, le=99)
    source_agent_id: str = Field(default="api-client", max_length=128)


class NetworkPrintClaimRequest(BaseModel):
    agent_id: str = Field(..., min_length=8, max_length=128)
    printers: List[str] = Field(default_factory=list, max_length=100)


class NetworkPrintStatusRequest(BaseModel):
    agent_id: str = Field(..., min_length=8, max_length=128)
    status: str = Field(..., pattern="^(completed|failed)$")
    error_message: str = Field(default="", max_length=1000)


def _require_printer_lan(request: Request) -> None:
    from server.printer_security import require_lan_address

    try:
        require_lan_address(request.client.host if request.client else "")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _require_printer_admin(request: Request, key: str | None) -> None:
    from server.printer_security import require_admin_key

    _require_printer_lan(request)
    try:
        require_admin_key(key)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _require_printer_client(request: Request, key: str | None) -> None:
    from server.printer_security import require_client_key

    _require_printer_lan(request)
    try:
        require_client_key(key)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/printer/agents/enroll")
def enroll_printer_agent(
    payload: PrinterAgentEnrollment,
    request: Request,
    x_printer_enrollment_key: Optional[str] = Header(default=None),
):
    from server.printer_security import require_enrollment_key
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    try:
        require_enrollment_key(x_printer_enrollment_key)
        agent, token = PrinterRegistry().enroll_agent(payload.agent_id, payload.computer_name)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": {"agent": agent, "agent_key": token}}


@app.post("/api/printer/agents/heartbeat")
def printer_agent_heartbeat(
    payload: PrinterAgentHeartbeat,
    request: Request,
    x_printer_agent_key: Optional[str] = Header(default=None),
):
    """Register one PC and its currently installed Windows printers."""
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    registry = PrinterRegistry()
    try:
        registry.authorize_agent(payload.agent_id, x_printer_agent_key or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    source_ip = request.client.host if request.client else payload.ip_address
    agent = registry.heartbeat(
        agent_id=payload.agent_id,
        computer_name=payload.computer_name,
        ip_address=source_ip or payload.ip_address,
        platform=payload.platform,
        agent_version=payload.agent_version,
        printers=[item.model_dump() for item in payload.printers],
    )
    return {"status": "SUCCESS", "data": agent}


@app.get("/api/printer/agents")
def printer_agents(request: Request, x_printer_api_key: Optional[str] = Header(default=None)):
    """List registered PCs, printers, and computed online/offline status."""
    from server.printer_service import PrinterRegistry

    _require_printer_client(request, x_printer_api_key)
    return {"status": "SUCCESS", "data": PrinterRegistry().list_agents()}


@app.put("/api/printer/agents/{agent_id}/permissions")
def update_printer_agent_permissions(
    agent_id: str,
    payload: PrinterAgentPermissions,
    request: Request,
    x_printer_api_key: Optional[str] = Header(default=None),
):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    try:
        agent = PrinterRegistry().set_agent_permissions(agent_id, payload.enabled, payload.allowed_job_types)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": agent}


@app.put("/api/printer/agents/{agent_id}/printers/permissions")
def update_network_printer_permissions(
    agent_id: str,
    payload: NetworkPrinterPermissions,
    request: Request,
    x_printer_api_key: Optional[str] = Header(default=None),
):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    try:
        agent = PrinterRegistry().set_printer_enabled(agent_id, payload.printer_name, payload.enabled)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": agent}


@app.get("/api/printer/security-audit")
def printer_security_audit(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    x_printer_api_key: Optional[str] = Header(default=None),
):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    return {"status": "SUCCESS", "data": PrinterRegistry().security_audit(limit)}


@app.post("/api/printer/jobs")
def create_network_print_job(payload: NetworkPrintJobRequest, request: Request, x_printer_api_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_client(request, x_printer_api_key)
    try:
        job = PrinterRegistry().create_job(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": job}


@app.post("/api/printer/jobs/upload")
async def upload_network_print_job(
    request: Request,
    file: UploadFile = File(...),
    target_agent_id: str = Form(...),
    printer_name: str = Form(...),
    request_key: str = Form(...),
    copies: int = Form(default=1),
    paper_size: str = Form(default="A4"),
    custom_width_mm: float = Form(default=210.0),
    custom_height_mm: float = Form(default=297.0),
    borderless: bool = Form(default=False),
    orientation: str = Form(default="portrait"),
    quality: str = Form(default="normal"),
    paper_type: str = Form(default="automatic"),
    color_mode: str = Form(default="color"),
    source_agent_id: str = Form(default="api-client"),
    x_printer_api_key: Optional[str] = Header(default=None),
):
    """Store a Phase 3 document and enqueue it for the selected remote printer."""
    from server.printer_assets import MAX_PRINT_ASSET_BYTES, store_asset
    from server.printer_service import PrinterRegistry

    _require_printer_client(request, x_printer_api_key)
    paper_size = str(paper_size or "A4").upper()
    orientation = str(orientation or "portrait").lower()
    if paper_size not in {"A4", "A5", "LETTER", "4X6", "5X7", "58MM", "80MM", "CUSTOM"}:
        raise HTTPException(
            status_code=400,
            detail="paper_size must be A4, A5, Letter, 4x6, 5x7, 58mm, 80mm, or Custom",
        )
    if paper_size == "CUSTOM" and not (
        20.0 <= custom_width_mm <= 1000.0 and 20.0 <= custom_height_mm <= 1000.0
    ):
        raise HTTPException(status_code=400, detail="custom paper dimensions must be between 20 and 1000 mm")
    if orientation not in {"portrait", "landscape"}:
        raise HTTPException(status_code=400, detail="orientation must be portrait or landscape")
    quality = str(quality or "normal").lower()
    paper_type = str(paper_type or "automatic").lower()
    color_mode = str(color_mode or "color").lower()
    if quality not in {"draft", "normal", "high"}:
        raise HTTPException(status_code=400, detail="quality must be draft, normal, or high")
    if paper_type not in {"driver_default", "automatic", "plain", "photo", "glossy", "matte"}:
        raise HTTPException(status_code=400, detail="Unsupported paper_type")
    if color_mode not in {"color", "grayscale"}:
        raise HTTPException(status_code=400, detail="color_mode must be color or grayscale")
    data = await file.read(MAX_PRINT_ASSET_BYTES + 1)
    asset_path = None
    try:
        registry = PrinterRegistry()
        existing = registry.get_job_by_request_key(request_key)
        if existing:
            return {"status": "SUCCESS", "data": existing}
        asset_id, asset_path, job_type = store_asset(file.filename or "", data)
        job = registry.create_job(
            request_key=request_key,
            target_agent_id=target_agent_id,
            printer_name=printer_name,
            job_type=job_type,
            payload={
                "asset_id": asset_id,
                "asset_path": asset_path,
                "filename": file.filename or "document",
                "paper_size": paper_size,
                "custom_width_mm": float(custom_width_mm),
                "custom_height_mm": float(custom_height_mm),
                "borderless": bool(borderless),
                "orientation": orientation,
                "quality": quality,
                "paper_type": paper_type,
                "color_mode": color_mode,
            },
            copies=copies,
            source_agent_id=source_agent_id,
        )
    except ValueError as exc:
        if asset_path:
            Path(asset_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        if asset_path:
            Path(asset_path).unlink(missing_ok=True)
        raise
    return {"status": "SUCCESS", "data": job}


@app.get("/api/printer/jobs")
def network_print_jobs(request: Request, limit: int = Query(default=100, ge=1, le=500), x_printer_api_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    return {"status": "SUCCESS", "data": PrinterRegistry().list_jobs(limit)}


@app.get("/api/printer/agents/{agent_id}/jobs")
def pending_network_print_jobs(agent_id: str, request: Request, limit: int = Query(default=5, ge=1, le=50), x_printer_agent_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    registry = PrinterRegistry()
    try:
        registry.authorize_agent(agent_id, x_printer_agent_key or "")
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": registry.pending_jobs(agent_id, limit)}


@app.post("/api/printer/jobs/{job_id}/claim")
def claim_network_print_job(job_id: str, payload: NetworkPrintClaimRequest, request: Request, x_printer_agent_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    registry = PrinterRegistry()
    try:
        current = registry.get_job(job_id)
        registry.authorize_agent(payload.agent_id, x_printer_agent_key or "", (current or {}).get("job_type", ""))
        job = registry.claim_job(job_id, payload.agent_id, payload.printers)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": job}


@app.post("/api/printer/jobs/{job_id}/status")
def update_network_print_job(job_id: str, payload: NetworkPrintStatusRequest, request: Request, x_printer_agent_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    registry = PrinterRegistry()
    try:
        registry.authorize_agent(payload.agent_id, x_printer_agent_key or "")
        job = registry.finish_job(job_id, payload.agent_id, payload.status, payload.error_message)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": job}


@app.post("/api/printer/jobs/{job_id}/retry")
def retry_network_print_job(job_id: str, request: Request, x_printer_api_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    try:
        job = PrinterRegistry().retry_job(job_id, "api-client")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "SUCCESS", "data": job}


@app.get("/api/printer/jobs/{job_id}/audit")
def network_print_job_audit(job_id: str, request: Request, x_printer_api_key: Optional[str] = Header(default=None)):
    from server.printer_service import PrinterRegistry

    _require_printer_admin(request, x_printer_api_key)
    return {"status": "SUCCESS", "data": PrinterRegistry().job_audit(job_id)}


@app.get("/api/printer/jobs/{job_id}/content")
def network_print_job_content(job_id: str, request: Request, x_printer_agent_id: Optional[str] = Header(default=None), x_printer_agent_key: Optional[str] = Header(default=None)):
    from server.printer_assets import resolve_asset
    from server.printer_service import PrinterRegistry

    _require_printer_lan(request)
    registry = PrinterRegistry()
    job = registry.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found")
    path_value = (job.get("payload") or {}).get("asset_path")
    if not path_value:
        raise HTTPException(status_code=404, detail="This print job has no document content")
    try:
        path = resolve_asset(path_value)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=(job.get("payload") or {}).get("filename") or path.name)


def _check_car_print_rate(request: Request, maximum=8, window_seconds=60) -> None:
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [stamp for stamp in _CAR_PRINT_RATE.get(address, []) if now - stamp < window_seconds]
    if len(recent) >= maximum:
        raise HTTPException(status_code=429, detail="Too many print requests. Please wait and try again.")
    recent.append(now)
    _CAR_PRINT_RATE[address] = recent


def _check_car_search_rate(request: Request, maximum=20, window_seconds=60) -> None:
    address = request.client.host if request.client else "unknown"
    now = time.monotonic()
    recent = [stamp for stamp in _CAR_SEARCH_RATE.get(address, []) if now - stamp < window_seconds]
    if len(recent) >= maximum:
        raise HTTPException(status_code=429, detail="Too many searches. Please wait and try again.")
    recent.append(now)
    _CAR_SEARCH_RATE[address] = recent


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


@app.get("/api/car/qr/{token}")
def public_car_qr_lookup(token: str):
    """Resolve an opaque owner QR without exposing private driver fields."""
    from server.car_management_service import CarRepository

    record = CarRepository().resolve_qr_token(token)
    if not record:
        raise HTTPException(status_code=404, detail="QR code is invalid or disabled.")
    return {"status": "SUCCESS", "data": record}


@app.get("/api/car/search")
def public_car_search(request: Request, q: str = Query(..., min_length=2, max_length=100)):
    """Privacy-limited mobile search with short-lived print grants."""
    from server.car_management_service import CarRepository

    _check_car_search_rate(request)
    now = time.monotonic()
    for key, value in list(_CAR_SEARCH_GRANTS.items()):
        if float(value.get("expires", 0)) <= now:
            _CAR_SEARCH_GRANTS.pop(key, None)
    try:
        records = CarRepository().search_public_records(q, 10)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    results = []
    for record in records:
        grant = secrets.token_urlsafe(32)
        _CAR_SEARCH_GRANTS[grant] = {"car_id": int(record["id"]), "expires": now + 600}
        public = {key: value for key, value in record.items() if key != "id"}
        public["grant"] = grant
        results.append(public)
    return {"status": "SUCCESS", "data": results}


@app.post("/api/car/print-jobs")
def create_public_car_print_job(payload: CarPrintRequest, request: Request):
    from server.car_management_service import CarRepository

    _check_car_print_rate(request)
    try:
        job = CarRepository().create_print_job(
            payload.token, payload.request_key, payload.copies, payload.printer_name
        )
        return {"status": "SUCCESS", "data": job}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/car/search-print-jobs")
def create_searched_car_print_job(payload: CarSearchPrintRequest, request: Request):
    """Create a print job from a temporary search grant without exposing QR tokens."""
    from server.car_management_service import CarRepository

    _check_car_print_rate(request)
    grant = _CAR_SEARCH_GRANTS.get(payload.grant)
    if not grant or float(grant.get("expires", 0)) <= time.monotonic():
        _CAR_SEARCH_GRANTS.pop(payload.grant, None)
        raise HTTPException(status_code=400, detail="Search selection expired. Search again.")
    repository = CarRepository()
    try:
        issued = repository.issue_qr_token(int(grant["car_id"]))
        job = repository.create_print_job(
            issued["token"], payload.request_key, payload.copies, payload.printer_name
        )
        _CAR_SEARCH_GRANTS.pop(payload.grant, None)
        return {"status": "SUCCESS", "data": job}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/car/printers")
def public_car_print_printers():
    from server.car_management_service import CarRepository

    printers = CarRepository().available_print_printers()
    return {"status": "SUCCESS", "data": printers}


@app.get("/api/car/print-jobs/{job_id}")
def public_car_print_job_status(job_id: str):
    from server.car_management_service import CarRepository

    job = CarRepository().get_print_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Print job not found.")
    return {"status": "SUCCESS", "data": job}


@app.get("/car/print", response_class=HTMLResponse)
def car_owner_print_page():
    """Mobile/kiosk page opened by an owner's secure car QR code."""
    return FileResponse(STATIC_DIR / "car_print.html", headers={"Cache-Control": "no-store"})


@app.get("/car", response_class=HTMLResponse)
def car_mobile_home_page():
    return FileResponse(STATIC_DIR / "car_kiosk.html", headers={"Cache-Control": "no-store"})


@app.get("/car/kiosk", response_class=HTMLResponse)
def car_print_kiosk_page():
    return FileResponse(STATIC_DIR / "car_kiosk.html", headers={"Cache-Control": "no-store"})


class CartItem(BaseModel):
    product_id: int = Field(..., gt=0)
    variant_id: Optional[int] = Field(default=None, gt=0)
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
    due_date: str = Field(default="", max_length=10)
    credit_notes: str = Field(default="", max_length=2000)
    allow_credit_over_limit: bool = False


class RefundRequest(BaseModel):
    reason: str = Field(default="Customer return", max_length=500)


class StockAdjustmentRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    variant_id: Optional[int] = Field(default=None, gt=0)
    adjustment: int = Field(..., ge=-1000000, le=1000000)
    reason: str = Field(default="Lite POS adjustment", max_length=500)
    location: str = Field(default="Shop", max_length=200)
    supplier_id: Optional[int] = Field(default=None, gt=0)
    unit_cost: float = Field(default=0, ge=0)
    batch_no: str = Field(default="", max_length=100)
    received_by: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    customer_id: Optional[int] = Field(default=None, gt=0)
    reference: str = Field(default="", max_length=200)
    issued_by: str = Field(default="", max_length=200)
    transaction_date: str = Field(default="", max_length=10)


class ExpenseRequest(BaseModel):
    category: str
    description: str = ""
    amount: float = Field(..., gt=0)
    expense_date: str = ""
    payment_method: str = "Cash"
    reference_no: str = ""
    notes: str = ""


class StockAdjustmentSetRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    variant_id: Optional[int] = Field(default=None, gt=0)
    new_quantity: int = Field(..., ge=0, le=1000000)
    adjustment_type: str = Field(default="Add", max_length=20)
    reason: str = Field(..., min_length=1, max_length=500)
    adjusted_by: str = Field(..., min_length=1, max_length=200)
    transaction_date: str = Field(default="", max_length=10)
    location: str = Field(default="Shop", max_length=200)
    notes: str = Field(default="", max_length=2000)
    location_only: bool = False


class StockTransferRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    from_location: str = Field(..., min_length=1, max_length=200)
    to_location: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(..., gt=0, le=1000000)
    reason: str = Field(..., min_length=1, max_length=500)
    reference: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)


class MovementReverseRequest(BaseModel):
    reason: str = Field(default="User requested reversal", min_length=1, max_length=500)


class ProductVariantRequest(BaseModel):
    color: str = ""
    size: str = ""
    sku: str = ""
    barcode: str = ""
    price: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    stock: int = Field(default=0, ge=0)
    low_stock: int = Field(default=0, ge=0)
    active: bool = True


class ProductManageRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    category: str = ""
    description: str = ""
    sold_by: str = "Each"
    price: float = Field(default=0, ge=0)
    cost: float = Field(default=0, ge=0)
    sku: str = ""
    barcode: str = ""
    stock: int = Field(default=0, ge=0)
    low_stock: int = Field(default=0, ge=0)
    unit: str = "pcs"
    base_unit: str = "pcs"
    pack_unit: str = ""
    pack_size: int = Field(default=1, ge=1)
    image_base64: str = ""
    image_filename: str = ""
    image_mime: str = ""
    variants: List[ProductVariantRequest] = Field(default_factory=list)


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


@app.get("/api/categories/manage")
def managed_categories(_: Dict[str, Any] = Depends(current_user)):
    return {"categories": cashier_service.list_managed_categories()}


@app.post("/api/categories/manage")
def create_managed_category(payload: CategoryManageRequest, _: Dict[str, Any] = Depends(current_user)):
    try:
        return {"category": cashier_service.create_managed_category(payload.dict())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/categories/manage/{category_id}")
def update_managed_category(category_id: int, payload: CategoryManageRequest, _: Dict[str, Any] = Depends(current_user)):
    try:
        return {"category": cashier_service.update_managed_category(category_id, payload.dict())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/categories/manage/{category_id}")
def delete_managed_category(category_id: int, _: Dict[str, Any] = Depends(current_user)):
    try:
        cashier_service.delete_managed_category(category_id)
        return {"deleted": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/products")
def products(
    q: str = Query(default=""),
    category: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: Dict[str, Any] = Depends(current_user),
):
    return {"products": cashier_service.list_products(q.strip(), category.strip(), limit, offset)}


@app.post("/api/products/manage")
def create_managed_product(payload: ProductManageRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"product": cashier_service.save_managed_product(payload.dict(), created_by=user.get("username", "Lite POS"))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/products/manage/{product_id}")
def update_managed_product(product_id: int, payload: ProductManageRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"product": cashier_service.save_managed_product(payload.dict(), product_id=product_id, created_by=user.get("username", "Lite POS"))}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/products/barcode/{barcode}")
def product_by_barcode(barcode: str, _: Dict[str, Any] = Depends(current_user)):
    return {"product": cashier_service.barcode_exists(barcode.strip())}


@app.get("/api/products/scan/{code}")
def scan_product(code: str, _: Dict[str, Any] = Depends(current_user)):
    return {"product": cashier_service.scan_product(code.strip())}


@app.post("/api/stock/adjust")
def adjust_stock(payload: StockAdjustmentRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"product": cashier_service.adjust_stock(
            product_id=payload.product_id, variant_id=payload.variant_id,
            adjustment=payload.adjustment, reason=payload.reason,
            location=payload.location, supplier_id=payload.supplier_id,
            unit_cost=payload.unit_cost, batch_no=payload.batch_no,
            received_by=payload.received_by, notes=payload.notes,
            customer_id=payload.customer_id, reference=payload.reference,
            issued_by=payload.issued_by, transaction_date=payload.transaction_date,
            created_by=user.get("username", "Lite POS"),
        )}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stock/adjustment")
def set_stock_adjustment(payload: StockAdjustmentSetRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"product": cashier_service.set_stock_quantity(
            **payload.dict(), created_by=user.get("username", "Lite POS")
        )}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/stock/transfer")
def transfer_stock(payload: StockTransferRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"product": cashier_service.transfer_stock(
            **payload.dict(), created_by=user.get("username", "Lite POS")
        )}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/stock/movements")
def stock_movements(
    product_id: int = Query(..., gt=0), limit: int = Query(default=200, ge=1, le=500),
    _: Dict[str, Any] = Depends(current_user),
):
    return {"movements": cashier_service.list_stock_movements(product_id, limit)}


@app.post("/api/stock/movements/{movement_id}/reverse")
def reverse_movement(
    movement_id: int, payload: MovementReverseRequest,
    user: Dict[str, Any] = Depends(current_user),
):
    try:
        return cashier_service.reverse_stock_movement_safe(
            movement_id, payload.reason, user.get("username", "Lite POS")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.get("/api/credit/settings")
def credit_settings(_: Dict[str, Any] = Depends(current_user)):
    return {"settings": cashier_service.get_credit_settings()}


@app.get("/api/suppliers")
def suppliers(_: Dict[str, Any] = Depends(current_user)):
    return {"suppliers": cashier_service.list_suppliers()}


@app.get("/api/stock/locations")
def stock_locations(_: Dict[str, Any] = Depends(current_user)):
    return {"locations": cashier_service.list_stock_locations()}


@app.get("/api/settings/cashier")
def cashier_settings(_: Dict[str, Any] = Depends(current_user)):
    return {"settings": cashier_service.get_cashier_settings()}


def _require_manager(user: Dict[str, Any]) -> None:
    if str(user.get("role") or "").casefold() not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Manager or Admin access is required.")


def _require_admin(user: Dict[str, Any]) -> None:
    if str(user.get("role") or "").casefold() != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")


@app.get("/api/settings/lite")
def lite_settings(user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    return {"settings": cashier_service.get_lite_settings()}


@app.put("/api/settings/lite")
def update_lite_settings(payload: LiteSettingsRequest, user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    try:
        return {"settings": cashier_service.save_lite_settings(payload.settings)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/settings/payment-types")
def payment_type_records(user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    return {"payment_types": cashier_service.list_payment_type_records()}


@app.post("/api/settings/payment-types")
def create_payment_type(payload: PaymentTypeRequest, user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    try: return {"payment_type": cashier_service.save_payment_type(payload.name)}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/settings/payment-types/{payment_id}")
def update_payment_type(payment_id: int, payload: PaymentTypeRequest, user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    try: return {"payment_type": cashier_service.save_payment_type(payload.name, payment_id)}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/settings/payment-types/{payment_id}")
def remove_payment_type(payment_id: int, user: Dict[str, Any] = Depends(current_user)):
    _require_manager(user)
    try: cashier_service.delete_payment_type(payment_id); return {"status": "SUCCESS"}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/settings/users")
def lite_users(user: Dict[str, Any] = Depends(current_user)):
    _require_admin(user)
    return {"users": cashier_service.list_lite_users(), "roles": cashier_service.list_user_roles()}


@app.post("/api/settings/users")
def create_lite_user(payload: LiteUserRequest, user: Dict[str, Any] = Depends(current_user)):
    _require_admin(user)
    try: return {"user": cashier_service.save_lite_user(payload.dict())}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/settings/users/{user_id}")
def update_lite_user(user_id: int, payload: LiteUserRequest, user: Dict[str, Any] = Depends(current_user)):
    _require_admin(user)
    try: return {"user": cashier_service.save_lite_user(payload.dict(), user_id)}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/settings/users/{user_id}")
def remove_lite_user(user_id: int, user: Dict[str, Any] = Depends(current_user)):
    _require_admin(user)
    try: cashier_service.delete_lite_user(user_id, int(user.get("id") or 0)); return {"status": "SUCCESS"}
    except Exception as exc: raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/expenses/categories")
def expense_categories(_: Dict[str, Any] = Depends(current_user)):
    return {"categories": cashier_service.list_expense_categories()}


@app.get("/api/expenses")
def expenses(
    q: str = Query(default="", max_length=200),
    from_date: str = Query(default="", max_length=10),
    to_date: str = Query(default="", max_length=10),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Dict[str, Any] = Depends(current_user),
):
    return cashier_service.list_expenses(q, from_date, to_date, limit, offset)


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
            due_date=payload.due_date,
            credit_notes=payload.credit_notes,
            allow_credit_over_limit=payload.allow_credit_over_limit,
            created_by=user.get("username", "Browser Cashier"),
        )
        return {"receipt": receipt}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Browser cashier checkout failed")
        raise HTTPException(status_code=500, detail=f"Checkout failed: {exc}") from exc


@app.post("/api/sales/{sale_id}/refund")
def refund_sale(sale_id: int, payload: RefundRequest, user: Dict[str, Any] = Depends(current_user)):
    try:
        return {"receipt": cashier_service.refund_sale(
            sale_id, payload.reason, user.get("username", "Lite POS")
        )}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Lite POS refund failed")
        raise HTTPException(status_code=500, detail=f"Refund failed: {exc}") from exc


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
    if x_printer_agent_id != job.get("target_agent_id"):
        raise HTTPException(status_code=403, detail="Print document is assigned to another agent")
    try:
        registry.authorize_agent(x_printer_agent_id or "", x_printer_agent_key or "", job.get("job_type", ""))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
