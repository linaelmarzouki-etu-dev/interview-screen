from __future__ import annotations

import asyncio
import json
import logging
import secrets
import socket
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from interview_assistent.agent_hub import LaptopAgentHub
from interview_assistent.config import Settings
from interview_assistent.events import EventBus
from interview_assistent.license.auth import LicenseContext, build_license_dependency, extract_token
from interview_assistent.license.keys import is_valid_key_format, normalize_key, share_url
from interview_assistent.license.plans import DEFAULT_PLAN, PLANS
from interview_assistent.license.store import LicenseStore

if TYPE_CHECKING:
    from interview_assistent.mcq_pipeline import McqPipeline
    from interview_assistent.pipeline import InterviewPipeline

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
_admin_tokens: set[str] = set()


class AnswerRequest(BaseModel):
    question: str | None = None


class ActivateRequest(BaseModel):
    key: str = Field(min_length=8, max_length=8)


class AdminLoginRequest(BaseModel):
    password: str


class GenerateKeysRequest(BaseModel):
    plan: str = DEFAULT_PLAN
    count: int = Field(default=1, ge=1, le=100)
    email: str = ""
    notes: str = ""


class RevokeKeyRequest(BaseModel):
    key: str | None = None
    prefix: str | None = None


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def create_app(
    settings: Settings,
    bus: EventBus,
    pipeline: InterviewPipeline | None = None,
    mcq_pipeline: McqPipeline | None = None,
) -> FastAPI:
    app = FastAPI(title="Interview Assistant", version="0.3.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    agent_hub = LaptopAgentHub()
    license_store = LicenseStore(
        Path(settings.license_db_path),
        settings.license_pepper,
    )
    license_enabled = settings.license_required and settings.mode == "mcq"
    optional_license = build_license_dependency(license_store, required=False)
    require_license = build_license_dependency(license_store, required=license_enabled)

    def _client_meta(request: Request) -> tuple[str, str]:
        ip = request.client.host if request.client else ""
        user_agent = request.headers.get("user-agent", "")
        return ip, user_agent

    def _require_admin(request: Request) -> None:
        token = request.headers.get("x-admin-token", "")
        if not token or token not in _admin_tokens:
            raise HTTPException(status_code=401, detail="Admin login required")

    def _public_base(request: Request) -> str:
        if settings.public_url:
            return settings.public_url.rstrip("/")
        host = request.headers.get("host") or f"{local_ip()}:{settings.port}"
        scheme = request.url.scheme if request.url.scheme in {"http", "https"} else "http"
        return f"{scheme}://{host}"

    async def _resolve_mcq_license(
        request: Request,
        license_ctx: LicenseContext | None = Depends(require_license),
    ) -> LicenseContext | None:
        if license_ctx is not None:
            return license_ctx
        if not license_enabled:
            return None
        license_id = agent_hub.consume_pending_grab()
        if license_id is None:
            raise HTTPException(
                status_code=401,
                detail="License required. Enter your 8-letter key.",
            )
        license_row = license_store.get_license_by_id(license_id)
        if license_row is None:
            raise HTTPException(status_code=401, detail="Grab session expired. Try again.")
        try:
            license_store.ensure_license_usable(license_row)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return LicenseContext(license=license_row, via_agent=True)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> FileResponse:
        page = "mcq.html" if settings.mode == "mcq" else "index.html"
        return FileResponse(STATIC_DIR / page)

    @app.get("/login", response_class=HTMLResponse)
    async def login_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "login.html")

    @app.get("/u/{key}")
    async def user_license_link(key: str) -> RedirectResponse:
        normalized = normalize_key(key)
        if not is_valid_key_format(normalized):
            raise HTTPException(status_code=400, detail="Invalid license key format")
        return RedirectResponse(url=f"/login?key={normalized}", status_code=302)

    @app.get("/download", response_class=HTMLResponse)
    async def download_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "download.html")

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "admin.html")

    @app.get("/api/info")
    async def info(
        license_ctx: LicenseContext | None = Depends(optional_license),
    ) -> dict[str, str | int | bool | None]:
        payload: dict[str, str | int | bool | None] = {
            "mode": settings.mode,
            "role": settings.role,
            "companion_url": settings.public_url or f"http://{local_ip()}:{settings.port}",
            "public_url": settings.public_url or "",
            "local_url": f"http://127.0.0.1:{settings.port}",
            "auto_answer": settings.auto_answer,
            "desktop_grab": settings.mcq_allow_desktop_grab,
            "remote_grab": not settings.mcq_allow_desktop_grab,
            "agent_connected": agent_hub.is_connected(),
            "license_required": license_enabled,
        }
        if license_ctx is not None:
            remaining = license_store.questions_remaining(license_ctx.license)
            payload.update(
                {
                    "licensed": True,
                    "plan": license_ctx.license.plan,
                    "license_expires_at": license_ctx.license.expires_at,
                    "questions_remaining": remaining,
                }
            )
        else:
            payload["licensed"] = not license_enabled
        return payload

    @app.post("/api/license/activate")
    async def activate_license(payload: ActivateRequest, request: Request) -> dict:
        if not license_enabled:
            return {"status": "disabled", "token": "", "plan": "", "expires_at": ""}
        ip, user_agent = _client_meta(request)
        try:
            result = license_store.activate(
                payload.key,
                ip=ip,
                user_agent=user_agent,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "status": "ok",
            "token": result.token,
            "plan": result.plan,
            "expires_at": result.expires_at,
            "questions_remaining": result.questions_remaining,
            "key_prefix": result.key_prefix,
            "share_url": share_url(_public_base(request), payload.key),
        }

    @app.get("/api/license/me")
    async def license_me(
        license_ctx: LicenseContext | None = Depends(require_license),
    ) -> dict:
        if not license_enabled:
            return {"licensed": True, "license_required": False}
        if license_ctx is None:
            raise HTTPException(status_code=401, detail="Not licensed")
        remaining = license_store.questions_remaining(license_ctx.license)
        return {
            "licensed": True,
            "license_required": True,
            "plan": license_ctx.license.plan,
            "expires_at": license_ctx.license.expires_at,
            "questions_remaining": remaining,
            "key_prefix": license_ctx.license.key_prefix,
        }

    @app.post("/api/license/logout")
    async def logout_license(request: Request) -> dict[str, str]:
        token = extract_token(request, request.headers.get("X-License-Token"))
        if token:
            license_store.logout(token)
        return {"status": "ok"}

    @app.post("/api/admin/login")
    async def admin_login(payload: AdminLoginRequest) -> dict[str, str]:
        if not settings.license_admin_password:
            raise HTTPException(status_code=503, detail="Admin password not configured")
        if payload.password != settings.license_admin_password:
            raise HTTPException(status_code=401, detail="Invalid admin password")
        token = secrets.token_urlsafe(24)
        _admin_tokens.add(token)
        return {"status": "ok", "token": token}

    @app.post("/api/admin/keys/generate")
    async def admin_generate_keys(
        payload: GenerateKeysRequest,
        request: Request,
    ) -> dict:
        _require_admin(request)
        if payload.plan not in PLANS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown plan. Choose: {', '.join(PLANS)}",
            )
        created = []
        for _ in range(payload.count):
            key, record = license_store.create_license(
                payload.plan,
                customer_email=payload.email,
                notes=payload.notes,
            )
            base = _public_base(request)
            created.append(
                {
                    "key": key,
                    "plan": record.plan,
                    "expires_at": record.expires_at,
                    "questions_limit": record.questions_limit,
                    "prefix": record.key_prefix,
                    "share_url": share_url(base, key),
                }
            )
        return {"status": "ok", "keys": created}

    @app.get("/api/admin/keys")
    async def admin_list_keys(
        request: Request,
        active_only: bool = False,
    ) -> dict:
        _require_admin(request)
        licenses = license_store.list_licenses(active_only=active_only)
        return {
            "status": "ok",
            "licenses": [
                {
                    "prefix": item.key_prefix,
                    "plan": item.plan,
                    "status": item.status,
                    "expires_at": item.expires_at,
                    "questions_used": item.questions_used,
                    "questions_limit": item.questions_limit,
                    "customer_email": item.customer_email,
                    "created_at": item.created_at,
                    "notes": item.notes,
                }
                for item in licenses
            ],
        }

    @app.post("/api/admin/keys/revoke")
    async def admin_revoke_key(payload: RevokeKeyRequest, request: Request) -> dict:
        _require_admin(request)
        if payload.key:
            revoked = license_store.revoke_by_key(payload.key)
            if not revoked:
                raise HTTPException(status_code=404, detail="License not found")
            return {"status": "ok", "revoked": 1}
        if payload.prefix:
            count = license_store.revoke_by_prefix(payload.prefix)
            return {"status": "ok", "revoked": count}
        raise HTTPException(status_code=400, detail="Provide key or prefix")

    @app.post("/api/webhooks/gumroad")
    async def gumroad_webhook(request: Request) -> dict:
        if settings.gumroad_webhook_secret:
            provided = request.headers.get("x-gumroad-secret", "")
            if provided != settings.gumroad_webhook_secret:
                raise HTTPException(status_code=401, detail="Invalid webhook secret")

        form = await request.form()
        email = str(form.get("email", "") or form.get("purchase_email", ""))
        product = str(form.get("product_name", "") or form.get("permalink", ""))
        plan = DEFAULT_PLAN
        lowered = product.lower()
        if "7" in lowered and "day" in lowered:
            plan = "7d"
        elif "30" in lowered and "day" in lowered:
            plan = "30d"

        key, record = license_store.create_license(
            plan,
            customer_email=email,
            notes=f"Gumroad: {product}".strip(),
        )
        logger.info("Gumroad sale: email=%s plan=%s key=%s", email, plan, key)
        return {
            "status": "ok",
            "key": key,
            "plan": record.plan,
            "expires_at": record.expires_at,
            "email": email,
        }

    @app.post("/api/start")
    async def start_listening() -> dict[str, str]:
        if pipeline is None:
            return {"status": "not_available"}
        await pipeline.start()
        return {"status": "listening"}

    @app.post("/api/stop")
    async def stop_listening() -> dict[str, str]:
        if pipeline is None:
            return {"status": "not_available"}
        await pipeline.stop()
        return {"status": "stopped"}

    @app.post("/api/answer")
    async def manual_answer(payload: AnswerRequest) -> dict[str, str]:
        if pipeline is None:
            return {"status": "not_available"}
        await pipeline.request_answer(payload.question)
        return {"status": "queued"}

    @app.post("/api/mcq/analyze")
    async def mcq_analyze(
        image: UploadFile = File(...),
        license_ctx: LicenseContext | None = Depends(_resolve_mcq_license),
    ) -> dict[str, str]:
        if mcq_pipeline is None:
            raise HTTPException(status_code=404, detail="MCQ mode is not active")
        data = await image.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty image")
        try:
            await mcq_pipeline.analyze_image(data, source=image.filename or "upload")
            if license_ctx is not None:
                license_store.record_question(license_ctx.license_id)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.post("/api/mcq/screenshot")
    async def mcq_screenshot(
        license_ctx: LicenseContext | None = Depends(_resolve_mcq_license),
    ) -> dict[str, str]:
        if mcq_pipeline is None:
            raise HTTPException(status_code=404, detail="MCQ mode is not active")
        if not settings.mcq_allow_desktop_grab:
            raise HTTPException(
                status_code=400,
                detail="Grab desktop screen is not available on this server. Use Upload or Paste.",
            )
        try:
            await mcq_pipeline.capture_and_analyze()
            if license_ctx is not None:
                license_store.record_question(license_ctx.license_id)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok"}

    @app.post("/api/mcq/request-grab")
    async def mcq_request_grab(
        license_ctx: LicenseContext | None = Depends(_resolve_mcq_license),
    ) -> dict[str, str]:
        if mcq_pipeline is None:
            raise HTTPException(status_code=404, detail="MCQ mode is not active")
        license_id = license_ctx.license_id if license_ctx else None
        try:
            await agent_hub.request_grab(license_id=license_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await bus.set_status("thinking", "Laptop is capturing screen...")
        return {"status": "queued"}

    @app.websocket("/ws/agent")
    async def agent_endpoint(websocket: WebSocket) -> None:
        await agent_hub.register(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await agent_hub.unregister(websocket)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        if license_enabled:
            token = websocket.query_params.get("token", "").strip()
            if not token:
                await websocket.close(code=4401, reason="License required")
                return
            try:
                license_store.validate_token(token)
            except ValueError:
                await websocket.close(code=4401, reason="Invalid license")
                return

        await websocket.accept()
        queue = await bus.subscribe()
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    await websocket.send_text(json.dumps(message))
                except asyncio.TimeoutError:
                    await websocket.send_text(json.dumps({"type": "ping"}))
        except WebSocketDisconnect:
            pass
        finally:
            await bus.unsubscribe(queue)

    return app