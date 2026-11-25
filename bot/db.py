import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    gift_id TEXT NOT NULL,
    gift_stars INTEGER NOT NULL,
    price_usd REAL NOT NULL,
    invoice_id INTEGER,
    pay_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | paid | delivered | failed | expired
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class DB:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection

    async def init(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def create_order(self, user_id, recipient_id, gift_id, gift_stars, price_usd) -> int:
        cur = await self.conn.execute(
            "INSERT INTO orders (user_id, recipient_id, gift_id, gift_stars, price_usd) VALUES (?,?,?,?,?)",
            (user_id, recipient_id, gift_id, gift_stars, price_usd),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def set_invoice(self, order_id, invoice_id, pay_url):
        await self.conn.execute(
            "UPDATE orders SET invoice_id=?, pay_url=? WHERE id=?", (invoice_id, pay_url, order_id)
        )
        await self.conn.commit()

    async def claim_paid(self, order_id) -> bool:
        """Атомарно переводит pending -> paid. Защита от двойной выдачи."""
        cur = await self.conn.execute(
            "UPDATE orders SET status='paid' WHERE id=? AND status='pending'", (order_id,)
        )
        await self.conn.commit()
        return cur.rowcount == 1

    async def set_status(self, order_id, status, error=None):
        await self.conn.execute(
            "UPDATE orders SET status=?, error=? WHERE id=?", (status, error, order_id)
        )
        await self.conn.commit()

    async def get(self, order_id):
        cur = await self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cur.fetchone()

    async def pending(self):
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE status='pending' AND invoice_id IS NOT NULL"
        )
        return await cur.fetchall()

    async def stats(self):
        cur = await self.conn.execute(
            "SELECT status, COUNT(*) c, COALESCE(SUM(price_usd),0) s FROM orders GROUP BY status"
        )
        return await cur.fetchall()
