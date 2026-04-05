"""
aiohttp REST API server — exposes bot data to the landing site.
Runs on API_PORT alongside bot polling.

Endpoints:
  GET  /api/stories
  POST /api/stories
  GET  /api/stats
  POST /api/photo/upload
  GET  /api/photo/status/{task_id}
  POST /api/search
  POST /api/search/quick
  POST /api/order/create
  GET  /api/order/{order_id}
  POST /api/payment/webhook
  GET  /api/health
  Static: /files → data/processed, /results → data/results
"""
import asyncio
import json
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any

import aiohttp as aio
from aiohttp import web

from services.database import (
    VALID_PRODUCT_TYPES,
    create_order,
    create_photo_task,
    get_order,
    get_photo_task,
    get_stats,
    get_stories,
    record_payment,
    save_story,
    update_order_status,
    update_payment_status,
    update_photo_task,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed YooKassa IP prefixes for webhook verification
# ---------------------------------------------------------------------------
YOOKASSA_IP_PREFIXES = (
    "185.71.76.",
    "185.71.77.",
    "77.75.153.",
    "77.75.154.",
    "77.75.156.",
    "127.0.0.1",
)

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "tiff", "tif"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _json_response(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        content_type="application/json",
        status=status,
        headers=_cors_headers(),
    )


def _path_to_url(path: str | None, prefix: str) -> str | None:
    """Convert a filesystem path inside data/ to a public /files/... URL."""
    if not path:
        return None
    p = Path(path)
    try:
        rel = p.relative_to("data/processed")
        return f"/files/{rel}"
    except ValueError:
        pass
    try:
        rel = p.relative_to("data/results")
        return f"/results/{rel}"
    except ValueError:
        pass
    return f"/{prefix}/{p.name}"


# ---------------------------------------------------------------------------
# CORS preflight — shared handler for all routes
# ---------------------------------------------------------------------------

async def handle_options(_request: web.Request) -> web.Response:
    """Handle CORS preflight for all routes."""
    return web.Response(status=204, headers=_cors_headers())


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _process_photo(task_id: str, image_path: str) -> None:
    try:
        await update_photo_task(task_id, status="processing")
        from pipeline.photo_processor import PhotoProcessor  # noqa: PLC0415
        proc = PhotoProcessor(output_dir="data/processed")
        result = await proc.process_full(image_path, task_id)
        await update_photo_task(
            task_id,
            status="completed",
            restored_path=result.restored_path,
            colorized_path=result.colorized_path,
            animated_path=result.animated_path,
            watermarked_path=result.watermarked_path,
        )
        logger.info("Photo processing completed: task_id=%s", task_id)
    except Exception:
        logger.exception("Photo processing failed: task_id=%s", task_id)
        await update_photo_task(task_id, status="failed", error_message="Processing error")


async def _process_order(order_id: str) -> None:
    try:
        order = await get_order(order_id)
        await update_order_status(order_id, "processing")
        sq = order["search_query"]
        loop = asyncio.get_event_loop()
        from pipeline.research_pipeline import run_search  # noqa: PLC0415
        results = await loop.run_in_executor(
            None,
            partial(
                run_search,
                sq["last_name"],
                sq.get("first_name"),
                sq.get("middle_name"),
                sq.get("birth_year"),
            ),
        )
        from pipeline.report_generator import generate_html  # noqa: PLC0415
        html = generate_html(results)
        result_dir = Path("data/results") / order_id
        result_dir.mkdir(parents=True, exist_ok=True)
        report_path = result_dir / "report.html"
        report_path.write_text(html, encoding="utf-8")
        await update_order_status(order_id, "completed", result_path=str(report_path))
        logger.info("Order processing completed: order_id=%s", order_id)
    except Exception:
        logger.exception("Order processing failed: order_id=%s", order_id)


# ---------------------------------------------------------------------------
# YooKassa payment helper
# ---------------------------------------------------------------------------

async def _create_yookassa_payment(
    order_id: str,
    amount_kopecks: int,
    email: str,
) -> str | None:
    shop_id = os.environ.get("YOOKASSA_SHOP_ID")
    secret = os.environ.get("YOOKASSA_SECRET_KEY")
    if not shop_id or not secret:
        return None

    site_url = os.environ.get("SITE_URL", "https://pamyat9may.ru")
    amount_str = f"{amount_kopecks / 100:.2f}"
    auth = aio.BasicAuth(shop_id, secret)
    payload = {
        "amount": {"value": amount_str, "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": f"{site_url}/order/{order_id}/success",
        },
        "capture": True,
        "description": f"Заказ {order_id}",
        "receipt": {
            "customer": {"email": email},
            "items": [
                {
                    "description": "Услуга Память 9 Мая",
                    "amount": {"value": amount_str, "currency": "RUB"},
                    "vat_code": 1,
                    "quantity": "1",
                }
            ],
        },
        "metadata": {"order_id": order_id},
    }

    try:
        async with aio.ClientSession() as session:
            resp = await session.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                auth=auth,
                headers={"Idempotence-Key": order_id},
            )
            if resp.status == 200:
                data = await resp.json()
                await record_payment(order_id, data["id"], amount_kopecks, "pending")
                return data.get("confirmation", {}).get("confirmation_url")
            logger.error(
                "YooKassa payment creation failed: status=%s order_id=%s",
                resp.status,
                order_id,
            )
    except Exception:
        logger.exception("YooKassa request error: order_id=%s", order_id)

    return None


# ---------------------------------------------------------------------------
# Existing handlers (kept unchanged)
# ---------------------------------------------------------------------------

async def handle_get_stories(request: web.Request) -> web.Response:
    """GET /api/stories?limit=20&offset=0"""
    try:
        limit = min(int(request.rel_url.query.get("limit", 20)), 100)
        offset = max(int(request.rel_url.query.get("offset", 0)), 0)
    except (ValueError, TypeError):
        return _json_response({"error": "Invalid limit or offset"}, status=400)

    stories = await get_stories(limit=limit, offset=offset, approved_only=True)
    return _json_response(stories)


async def handle_get_stats(_request: web.Request) -> web.Response:
    """GET /api/stats"""
    stats = await get_stats()
    return _json_response(stats)


async def handle_post_story(request: web.Request) -> web.Response:
    """POST /api/stories — submit story from website."""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    hero_name: str = (body.get("hero_name") or "").strip()
    text: str = (body.get("text") or "").strip()
    author_name: str = (body.get("author_name") or "").strip()

    if not text:
        return _json_response({"error": "text is required"}, status=422)
    if len(text) > 4000:
        return _json_response({"error": "text is too long (max 4000 chars)"}, status=422)
    if len(hero_name) > 200:
        return _json_response({"error": "hero_name is too long (max 200 chars)"}, status=422)

    story_id = await save_story(
        user_id=None,
        user_name=author_name or None,
        hero_name=hero_name or None,
        text=text,
        photo_url=None,
    )
    logger.info("Story submitted via API: id=%s hero=%r", story_id, hero_name)
    return _json_response({"ok": True, "id": story_id}, status=201)


# ---------------------------------------------------------------------------
# New handlers
# ---------------------------------------------------------------------------

async def handle_photo_upload(request: web.Request) -> web.Response:
    """POST /api/photo/upload — multipart upload, returns task_id."""
    reader = await request.multipart()
    field = await reader.next()

    if field is None or field.name != "file":
        return _json_response({"error": "Field 'file' is required"}, status=400)

    filename = field.filename or "upload"
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        return _json_response(
            {"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"},
            status=415,
        )

    # Read file data with size limit
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await field.read_chunk(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_SIZE:
            return _json_response({"error": "File too large (max 20 MB)"}, status=413)
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        return _json_response({"error": "Empty file"}, status=400)

    # Persist to disk before creating the DB record
    uploads_dir = Path("data/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    import uuid  # noqa: PLC0415
    task_id = str(uuid.uuid4())
    save_path = uploads_dir / f"{task_id}.{ext}"
    save_path.write_bytes(data)

    await create_photo_task(order_id=None, original_path=str(save_path))
    asyncio.create_task(_process_photo(task_id, str(save_path)))

    logger.info("Photo upload accepted: task_id=%s path=%s", task_id, save_path)
    return _json_response({"task_id": task_id, "status": "pending"}, status=202)


async def handle_photo_status(request: web.Request) -> web.Response:
    """GET /api/photo/status/{task_id}"""
    task_id = request.match_info["task_id"]
    task = await get_photo_task(task_id)
    if not task:
        return _json_response({"error": "Task not found"}, status=404)

    urls = {
        "original": _path_to_url(task.get("original_path"), "files"),
        "restored": _path_to_url(task.get("restored_path"), "files"),
        "colorized": _path_to_url(task.get("colorized_path"), "files"),
        "animated": _path_to_url(task.get("animated_path"), "files"),
        "watermarked": _path_to_url(task.get("watermarked_path"), "files"),
    }

    return _json_response({
        "task_id": task_id,
        "status": task.get("status"),
        "error_message": task.get("error_message"),
        "urls": urls,
    })


async def handle_search(request: web.Request) -> web.Response:
    """POST /api/search — full search, returns complete results."""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    last_name: str = (body.get("last_name") or "").strip()
    if len(last_name) < 2:
        return _json_response(
            {"error": "last_name is required and must be at least 2 characters"}, status=422
        )

    first_name: str | None = (body.get("first_name") or "").strip() or None
    middle_name: str | None = (body.get("middle_name") or "").strip() or None
    birth_year: int | None = body.get("birth_year")

    from pipeline.research_pipeline import run_search  # noqa: PLC0415
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None,
            partial(run_search, last_name, first_name, middle_name, birth_year),
        )
    except Exception:
        logger.exception("Search failed: last_name=%r", last_name)
        return _json_response({"error": "Search failed"}, status=500)

    return _json_response(results)


async def handle_search_quick(request: web.Request) -> web.Response:
    """POST /api/search/quick — teaser endpoint, returns counts only."""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    last_name: str = (body.get("last_name") or "").strip()
    if len(last_name) < 2:
        return _json_response(
            {"error": "last_name is required and must be at least 2 characters"}, status=422
        )

    first_name: str | None = (body.get("first_name") or "").strip() or None
    middle_name: str | None = (body.get("middle_name") or "").strip() or None
    birth_year: int | None = body.get("birth_year")

    from pipeline.research_pipeline import run_search  # noqa: PLC0415
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None,
            partial(run_search, last_name, first_name, middle_name, birth_year),
        )
    except Exception:
        logger.exception("Quick search failed: last_name=%r", last_name)
        return _json_response({"error": "Search failed"}, status=500)

    total_awards: int = results.get("total_awards", 0)
    total_losses: int = results.get("total_losses", 0)
    return _json_response({
        "total": total_awards + total_losses,
        "awards": total_awards,
        "losses": total_losses,
    })


async def handle_order_create(request: web.Request) -> web.Response:
    """POST /api/order/create"""
    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    product_type: str = (body.get("product_type") or "").strip()
    if product_type not in VALID_PRODUCT_TYPES:
        return _json_response(
            {"error": f"Invalid product_type. Allowed: {', '.join(sorted(VALID_PRODUCT_TYPES))}"},
            status=422,
        )

    last_name: str = (body.get("last_name") or "").strip()
    if not last_name:
        return _json_response({"error": "last_name is required"}, status=422)

    first_name: str | None = (body.get("first_name") or "").strip() or None
    middle_name: str | None = (body.get("middle_name") or "").strip() or None
    birth_year: int | None = body.get("birth_year")
    contact_email: str = (body.get("contact_email") or "").strip()
    contact_phone: str | None = (body.get("contact_phone") or "").strip() or None
    total_price: int = int(body.get("total_price", 0))

    if not contact_email:
        return _json_response({"error": "contact_email is required"}, status=422)
    if total_price <= 0:
        return _json_response({"error": "total_price must be positive"}, status=422)

    try:
        order_id = await create_order(
            product_type=product_type,
            last_name=last_name,
            first_name=first_name,
            middle_name=middle_name,
            birth_year=birth_year,
            contact_email=contact_email,
            contact_phone=contact_phone,
            total_price=total_price,
        )
    except Exception:
        logger.exception("Order creation failed")
        return _json_response({"error": "Failed to create order"}, status=500)

    payment_url: str | None = None
    if os.environ.get("YOOKASSA_SHOP_ID"):
        payment_url = await _create_yookassa_payment(order_id, total_price, contact_email)

    logger.info(
        "Order created: order_id=%s product=%s email=%s",
        order_id, product_type, contact_email,
    )
    return _json_response(
        {"order_id": order_id, "status": "pending", "payment_url": payment_url},
        status=201,
    )


async def handle_order_get(request: web.Request) -> web.Response:
    """GET /api/order/{order_id}"""
    order_id = request.match_info["order_id"]
    order = await get_order(order_id)
    if not order:
        return _json_response({"error": "Order not found"}, status=404)

    return _json_response({
        "order_id": order_id,
        "product_type": order.get("product_type"),
        "status": order.get("status"),
        "total_price": order.get("total_price"),
        "created_at": order.get("created_at"),
        "completed_at": order.get("completed_at"),
        "result_available": bool(order.get("result_path")),
    })


async def handle_payment_webhook(request: web.Request) -> web.Response:
    """POST /api/payment/webhook — YooKassa webhook."""
    # IP whitelist check
    peername = request.transport.get_extra_info("peername")
    client_ip: str = peername[0] if peername else ""
    # Also check X-Forwarded-For for reverse-proxy deployments
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    check_ip = forwarded_for or client_ip

    if not any(check_ip.startswith(prefix) for prefix in YOOKASSA_IP_PREFIXES):
        logger.warning("Payment webhook rejected: IP=%s", check_ip)
        return _json_response({"error": "Forbidden"}, status=403)

    try:
        body = await request.json()
    except Exception:
        return _json_response({"error": "Invalid JSON body"}, status=400)

    obj = body.get("object", {})
    yookassa_id: str = obj.get("id", "")
    status: str = obj.get("status", "")
    metadata: dict = obj.get("metadata", {})
    order_id: str = metadata.get("order_id", "")

    if not order_id or not yookassa_id:
        logger.warning("Payment webhook missing order_id or payment id")
        return _json_response({"ok": True})

    logger.info(
        "Payment webhook: yookassa_id=%s status=%s order_id=%s",
        yookassa_id, status, order_id,
    )

    if status == "succeeded":
        await update_payment_status(yookassa_id, "succeeded")
        await update_order_status(order_id, "paid")
        asyncio.create_task(_process_order(order_id))
    elif status == "canceled":
        await update_payment_status(yookassa_id, "canceled")

    return _json_response({"ok": True})


async def handle_health(_request: web.Request) -> web.Response:
    """GET /api/health"""
    return _json_response({
        "status": "ok",
        "db": True,
        "yookassa": bool(os.environ.get("YOOKASSA_SHOP_ID")),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
    })


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def build_app() -> web.Application:
    """Construct and return the aiohttp Application."""
    # Ensure data directories exist
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    Path("data/uploads").mkdir(parents=True, exist_ok=True)
    Path("data/results").mkdir(parents=True, exist_ok=True)

    app = web.Application()

    # --- Static file serving ---
    app.router.add_static("/files", path="data/processed", name="files")
    app.router.add_static("/results", path="data/results", name="results")

    # --- OPTIONS preflight for every API path ---
    for path in (
        "/api/stories",
        "/api/stats",
        "/api/photo/upload",
        "/api/photo/status/{task_id}",
        "/api/search",
        "/api/search/quick",
        "/api/order/create",
        "/api/order/{order_id}",
        "/api/payment/webhook",
        "/api/health",
    ):
        app.router.add_route("OPTIONS", path, handle_options)

    # --- Existing endpoints ---
    app.router.add_get("/api/stories", handle_get_stories)
    app.router.add_get("/api/stats", handle_get_stats)
    app.router.add_post("/api/stories", handle_post_story)

    # --- New endpoints ---
    app.router.add_post("/api/photo/upload", handle_photo_upload)
    app.router.add_get("/api/photo/status/{task_id}", handle_photo_status)
    app.router.add_post("/api/search", handle_search)
    app.router.add_post("/api/search/quick", handle_search_quick)
    app.router.add_post("/api/order/create", handle_order_create)
    app.router.add_get("/api/order/{order_id}", handle_order_get)
    app.router.add_post("/api/payment/webhook", handle_payment_webhook)
    app.router.add_get("/api/health", handle_health)

    return app
