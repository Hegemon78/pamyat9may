"""
Database service — SQLite via aiosqlite.
Path: data/pamyat9may.db
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "pamyat9may.db"


async def init_db() -> None:
    """Initialize database schema and indexes."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS stories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                user_name   TEXT,
                hero_name   TEXT,
                text        TEXT NOT NULL,
                photo_url   TEXT,
                approved    BOOLEAN DEFAULT 1,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS quiz_results (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER,
                user_name    TEXT,
                score        INTEGER,
                total        INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER UNIQUE,
                first_name TEXT,
                username   TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen  TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_stories_created_at
                ON stories (created_at);

            CREATE INDEX IF NOT EXISTS idx_users_user_id
                ON users (user_id);

            -- Commercial pipeline tables
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                product_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                contact_email TEXT,
                contact_phone TEXT,
                search_query TEXT,
                result_path TEXT,
                total_price INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                paid_at TEXT,
                processing_started_at TEXT,
                completed_at TEXT,
                delivered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS photo_tasks (
                id TEXT PRIMARY KEY,
                order_id TEXT,
                original_path TEXT NOT NULL,
                restored_path TEXT,
                colorized_path TEXT,
                animated_path TEXT,
                watermarked_path TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                yookassa_id TEXT,
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders (status);
            CREATE INDEX IF NOT EXISTS idx_photo_tasks_status
                ON photo_tasks (status);
        """)
        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def save_story(
    user_id: Optional[int],
    user_name: Optional[str],
    hero_name: Optional[str],
    text: str,
    photo_url: Optional[str] = None,
) -> int:
    """Save memorial story. Returns new row id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO stories (user_id, user_name, hero_name, text, photo_url)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, user_name, hero_name, text, photo_url),
        )
        await db.commit()
        return cursor.lastrowid


async def get_stories(
    limit: int = 20,
    offset: int = 0,
    approved_only: bool = True,
) -> list[dict[str, Any]]:
    """Fetch stories ordered by newest first."""
    query = """
        SELECT id, user_id, user_name, hero_name, text, photo_url, approved, created_at
        FROM stories
        {where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    where = "WHERE approved = 1" if approved_only else ""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query.format(where=where), (limit, offset))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_story_count(approved_only: bool = True) -> int:
    """Return total number of stories."""
    query = "SELECT COUNT(*) FROM stories" + (" WHERE approved = 1" if approved_only else "")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query)
        row = await cursor.fetchone()
        return row[0] if row else 0


async def save_quiz_result(
    user_id: Optional[int],
    user_name: Optional[str],
    score: int,
    total: int,
) -> None:
    """Save quiz completion result."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO quiz_results (user_id, user_name, score, total)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, user_name, score, total),
        )
        await db.commit()


async def get_leaderboard(limit: int = 10) -> list[dict[str, Any]]:
    """Return top quiz results per user (best score)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT user_name, MAX(score) AS best_score, total, MAX(completed_at) AS last_at
            FROM quiz_results
            GROUP BY user_id
            ORDER BY best_score DESC, last_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def upsert_user(
    user_id: int,
    first_name: str,
    username: Optional[str],
) -> None:
    """Insert or update user record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, first_name, username, last_seen)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                username   = excluded.username,
                last_seen  = CURRENT_TIMESTAMP
            """,
            (user_id, first_name, username),
        )
        await db.commit()


async def get_stats() -> dict[str, int]:
    """Return aggregate stats for API and /stats command."""
    async with aiosqlite.connect(DB_PATH) as db:
        stories_row = await (await db.execute(
            "SELECT COUNT(*) FROM stories WHERE approved = 1"
        )).fetchone()
        users_row = await (await db.execute(
            "SELECT COUNT(*) FROM users"
        )).fetchone()
        quiz_row = await (await db.execute(
            "SELECT COUNT(*) FROM quiz_results"
        )).fetchone()
        return {
            "stories": stories_row[0] if stories_row else 0,
            "users": users_row[0] if users_row else 0,
            "quiz_completions": quiz_row[0] if quiz_row else 0,
        }


# ============================================
# Commercial pipeline — orders, photo tasks, payments
# ============================================

VALID_PRODUCT_TYPES = {
    "free_search", "photo_revive", "photo_ai",
    "memorial_video", "combat_path", "family_memory",
}


async def create_order(
    product_type: str,
    search_query: dict,
    contact_email: str,
    contact_phone: Optional[str],
    total_price: int,
) -> str:
    """Create a new order. Returns order UUID."""
    order_id = uuid.uuid4().hex[:12]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO orders (id, product_type, search_query, contact_email, contact_phone, total_price)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, product_type, json.dumps(search_query, ensure_ascii=False),
             contact_email, contact_phone, total_price),
        )
        await db.commit()
    return order_id


async def get_order(order_id: str) -> Optional[dict[str, Any]]:
    """Get order by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("search_query"):
            d["search_query"] = json.loads(d["search_query"])
        return d


async def update_order_status(order_id: str, status: str, **kwargs: Any) -> None:
    """Update order status and optional fields."""
    ts_map = {
        "paid": "paid_at",
        "processing": "processing_started_at",
        "completed": "completed_at",
        "delivered": "delivered_at",
    }
    if status in ts_map:
        kwargs.setdefault(ts_map[status], datetime.utcnow().isoformat())

    sets = ["status = ?"]
    vals: list[Any] = [status]
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(order_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE orders SET {', '.join(sets)} WHERE id = ?", vals,
        )
        await db.commit()


async def create_photo_task(
    order_id: Optional[str],
    original_path: str,
) -> str:
    """Create a photo processing task. Returns task UUID."""
    task_id = uuid.uuid4().hex[:12]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO photo_tasks (id, order_id, original_path) VALUES (?, ?, ?)",
            (task_id, order_id, original_path),
        )
        await db.commit()
    return task_id


async def update_photo_task(task_id: str, **kwargs: Any) -> None:
    """Update photo task fields (status, paths, error)."""
    if kwargs.get("status") in ("completed", "failed"):
        kwargs.setdefault("completed_at", datetime.utcnow().isoformat())

    sets = []
    vals: list[Any] = []
    for k, v in kwargs.items():
        sets.append(f"{k} = ?")
        vals.append(v)
    vals.append(task_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE photo_tasks SET {', '.join(sets)} WHERE id = ?", vals,
        )
        await db.commit()


async def get_photo_task(task_id: str) -> Optional[dict[str, Any]]:
    """Get photo task by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM photo_tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def record_payment(
    order_id: str,
    yookassa_id: str,
    amount: int,
    status: str = "pending",
) -> str:
    """Record a payment. Returns payment UUID."""
    payment_id = uuid.uuid4().hex[:12]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments (id, order_id, yookassa_id, amount, status) VALUES (?, ?, ?, ?, ?)",
            (payment_id, order_id, yookassa_id, amount, status),
        )
        await db.commit()
    return payment_id


async def update_payment_status(yookassa_id: str, status: str) -> Optional[str]:
    """Update payment by YooKassa ID. Returns associated order_id."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT order_id FROM payments WHERE yookassa_id = ?", (yookassa_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        await db.execute(
            "UPDATE payments SET status = ? WHERE yookassa_id = ?",
            (status, yookassa_id),
        )
        await db.commit()
        return row[0]
