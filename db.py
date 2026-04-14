"""
Database module — uses Supabase (PostgreSQL via asyncpg) if DATABASE_URL is set,
otherwise falls back to local SQLite. All queries use the same interface.
"""
import os, sqlite3

DATABASE_URL = os.getenv("DATABASE_URL")  # set this in Render to use Supabase

# ─── detect mode ─────────────────────────────────────────────────────────────
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import asyncpg
    _pool = None

    async def init_pool():
        global _pool
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        print("Connected to Supabase (PostgreSQL)")

    async def get_pool():
        global _pool
        if _pool is None:
            await init_pool()
        return _pool

else:
    os.makedirs("data", exist_ok=True)
    DB_PATH = "data/craftbot.db"

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    print("Using local SQLite database")

# ─── schema ───────────────────────────────────────────────────────────────────
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS levels (
    guild_id TEXT, user_id TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS economy (
    guild_id TEXT, user_id TEXT, coins INTEGER DEFAULT 0, last_daily TEXT,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS shop (
    guild_id TEXT, item_id TEXT, name TEXT, price INTEGER,
    description TEXT, role_id INTEGER, stock INTEGER DEFAULT 0,
    stock_remaining INTEGER, cooldown_hours INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, item_id)
);
CREATE TABLE IF NOT EXISTS shop_purchases (
    guild_id TEXT, item_id TEXT, user_id TEXT, purchased_at TEXT
);
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT, user_id TEXT, reason TEXT, mod_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS tempbans (
    guild_id INTEGER, user_id INTEGER, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS config (
    guild_id TEXT, key TEXT, value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS markov (
    guild_id TEXT, user_id TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS tiktok_feeds (
    guild_id TEXT, username TEXT, channel_id INTEGER,
    role_id INTEGER, last_id TEXT,
    PRIMARY KEY (guild_id, username)
);
CREATE TABLE IF NOT EXISTS twitch_feeds (
    guild_id TEXT, username TEXT, channel_id INTEGER,
    role_id INTEGER, is_live INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, username)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT, name TEXT, description TEXT, event_time TEXT
);
CREATE TABLE IF NOT EXISTS xp_config (
    guild_id TEXT, key TEXT, value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS starboard (
    guild_id TEXT, message_id TEXT, sb_message_id TEXT,
    PRIMARY KEY (guild_id, message_id)
);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS levels (
    guild_id TEXT, user_id TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS economy (
    guild_id TEXT, user_id TEXT, coins INTEGER DEFAULT 0, last_daily TEXT,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS shop (
    guild_id TEXT, item_id TEXT, name TEXT, price INTEGER,
    description TEXT, role_id BIGINT, stock INTEGER DEFAULT 0,
    stock_remaining INTEGER, cooldown_hours INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, item_id)
);
CREATE TABLE IF NOT EXISTS shop_purchases (
    guild_id TEXT, item_id TEXT, user_id TEXT, purchased_at TEXT
);
CREATE TABLE IF NOT EXISTS warnings (
    id SERIAL PRIMARY KEY,
    guild_id TEXT, user_id TEXT, reason TEXT, mod_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS tempbans (
    guild_id BIGINT, user_id BIGINT, expires_at TEXT
);
CREATE TABLE IF NOT EXISTS config (
    guild_id TEXT, key TEXT, value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS markov (
    guild_id TEXT, user_id TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS tiktok_feeds (
    guild_id TEXT, username TEXT, channel_id BIGINT,
    role_id BIGINT, last_id TEXT,
    PRIMARY KEY (guild_id, username)
);
CREATE TABLE IF NOT EXISTS twitch_feeds (
    guild_id TEXT, username TEXT, channel_id BIGINT,
    role_id BIGINT, is_live INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, username)
);
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    guild_id TEXT, name TEXT, description TEXT, event_time TEXT
);
CREATE TABLE IF NOT EXISTS xp_config (
    guild_id TEXT, key TEXT, value TEXT,
    PRIMARY KEY (guild_id, key)
);
CREATE TABLE IF NOT EXISTS starboard (
    guild_id TEXT, message_id TEXT, sb_message_id TEXT,
    PRIMARY KEY (guild_id, message_id)
);
"""

# ─── init ─────────────────────────────────────────────────────────────────────
async def init_db():
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(POSTGRES_SCHEMA)
        print("Supabase tables ready")
    else:
        with get_db() as db:
            db.executescript(SQLITE_SCHEMA)
        print("SQLite tables ready")

# ─── unified query helpers ────────────────────────────────────────────────────
# These wrap both backends so cogs don't need to care which DB is active.

async def fetchone(query, params=()):
    """Fetch a single row."""
    query = _adapt(query)
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
            return dict(row) if row else None
    else:
        with get_db() as db:
            row = db.execute(query, params).fetchone()
            return dict(row) if row else None

async def fetchall(query, params=()):
    """Fetch all rows."""
    query = _adapt(query)
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]
    else:
        with get_db() as db:
            rows = db.execute(query, params).fetchall()
            return [dict(r) for r in rows]

async def execute(query, params=()):
    """Execute a write query."""
    query = _adapt(query)
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, *params)
    else:
        with get_db() as db:
            db.execute(query, params)

async def executemany(query, params_list):
    """Execute a write query with multiple param sets."""
    query = _adapt(query)
    if USE_POSTGRES:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(query, params_list)
    else:
        with get_db() as db:
            db.executemany(query, params_list)

def _adapt(query):
    """Convert SQLite ? placeholders to PostgreSQL $1, $2... if needed."""
    if not USE_POSTGRES:
        return query
    count = 0
    result = []
    for char in query:
        if char == "?":
            count += 1
            result.append(f"${count}")
        else:
            result.append(char)
    return "".join(result)

# ─── config helpers ───────────────────────────────────────────────────────────
async def get_config(guild_id, key, default=None):
    row = await fetchone("SELECT value FROM config WHERE guild_id=? AND key=?", (str(guild_id), key))
    return row["value"] if row else default

async def set_config(guild_id, key, value):
    if USE_POSTGRES:
        await execute(
            "INSERT INTO config (guild_id, key, value) VALUES (?,?,?) ON CONFLICT (guild_id, key) DO UPDATE SET value=EXCLUDED.value",
            (str(guild_id), key, str(value))
        )
    else:
        await execute("INSERT OR REPLACE INTO config (guild_id, key, value) VALUES (?,?,?)", (str(guild_id), key, str(value)))
