"""
Памяти 9 Мая — Telegram bot entry point.
Starts bot polling and aiohttp API server concurrently.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Load .env from the bot directory
load_dotenv(Path(__file__).parent / ".env")

# Configure logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Validate required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.critical(
        "BOT_TOKEN is not set. Copy .env.example to .env and set your token."
    )
    sys.exit(1)

API_PORT = int(os.getenv("API_PORT", "8081"))

# Optional pipeline env vars — warn if missing, but don't fail
for key in ("OPENROUTER_API_KEY", "FAL_API_KEY", "PALETTE_API_KEY", "DID_API_KEY"):
    if not os.getenv(key):
        logger.warning("%s not set — feature will use fallback", key)

for key in ("YOOKASSA_SHOP_ID", "YOOKASSA_SECRET_KEY"):
    if not os.getenv(key):
        logger.warning("%s not set — payments disabled", key)

# Create data directories
for d in ("data", "data/uploads", "data/processed", "data/results", "data/videos"):
    os.makedirs(d, exist_ok=True)

# Register routers after env validation (they import db helpers)
from handlers.start import router as start_router
from handlers.quiz import router as quiz_router
from handlers.story import router as story_router
from services.database import init_db
from services.api_server import build_app


async def run_api_server(app: web.Application, port: int) -> None:
    """Run aiohttp application without blocking the event loop."""
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("API server listening on port %d", port)
    # Keep running until cancelled
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    # Initialize DB
    await init_db()

    # Build bot and dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(story_router)

    # Build API app
    api_app = build_app()

    logger.info("Starting Памяти 9 Мая bot...")

    # Run both concurrently
    async with asyncio.TaskGroup() as tg:
        tg.create_task(run_api_server(api_app, API_PORT))
        tg.create_task(
            dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
            )
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
