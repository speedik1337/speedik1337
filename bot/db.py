import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,          -- в сумах
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS topups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    method TEXT NOT NULL,                        -- card | crypto | admin
    amount INTEGER NOT NULL,                     -- в сумах
    external_id TEXT,                            -- invoice_id CryptoBot / charge_id Telegram
    status TEXT NOT NULL DEFAULT 'pending',      -- pending | paid | expired
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    gift_id TEXT NOT NULL,
    gift_stars INTEGER NOT NULL,
    price INTEGER NOT NULL,                      -- в сумах
    status TEXT NOT NULL DEFAULT 'delivered',    -- delivered | refunded
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class DB:
    conn: aiosqlite.Connection

    async def init(self, path: str):
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    # --- пользователи / баланс ---
    async def ensure_user(self, uid: int):
        await self.conn.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (uid,))
        await self.conn.commit()

    async def balance(self, uid: int) -> int:
        cur = await self.conn.execute("SELECT balance FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        return row["balance"] if row else 0

    async def add_balance(self, uid: int, amount: int):
        await self.ensure_user(uid)
        await self.conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
        await self.conn.commit()

    async def charge(self, uid: int, amount: int) -> bool:
        """Атомарное списание: не уйдёт в минус даже при параллельных покупках."""
        cur = await self.conn.execute(
            "UPDATE users SET balance=balance-? WHERE id=? AND balance>=?", (amount, uid, amount)
        )
        await self.conn.commit()
        return cur.rowcount == 1

    # --- пополнения ---
    async def create_topup(self, uid: int, method: str, amount: int) -> int:
        cur = await self.conn.execute(
            "INSERT INTO topups (user_id, method, amount) VALUES (?,?,?)", (uid, method, amount)
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_topup(self, tid: int):
        cur = await self.conn.execute("SELECT * FROM topups WHERE id=?", (tid,))
        return await cur.fetchone()

    async def set_topup_external(self, tid: int, external_id: str):
        await self.conn.execute("UPDATE topups SET external_id=? WHERE id=?", (external_id, tid))
        await self.conn.commit()

    async def complete_topup(self, tid: int, external_id: str | None = None) -> bool:
        """pending -> paid и зачисление на баланс, ровно один раз."""
        cur = await self.conn.execute(
            "UPDATE topups SET status='paid', external_id=COALESCE(?, external_id) "
            "WHERE id=? AND status='pending'",
            (external_id, tid),
        )
        if cur.rowcount != 1:
            await self.conn.commit()
            return False
        t = await self.get_topup(tid)
        await self.conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (t["amount"], t["user_id"]))
        await self.conn.commit()
        return True

    async def expire_topup(self, tid: int):
        await self.conn.execute("UPDATE topups SET status='expired' WHERE id=? AND status='pending'", (tid,))
        await self.conn.commit()

    async def pending_crypto_topups(self):
        cur = await self.conn.execute(
            "SELECT * FROM topups WHERE method='crypto' AND status='pending' AND external_id IS NOT NULL"
        )
        return await cur.fetchall()

    # --- заказы ---
    async def create_order(self, uid, recipient_id, gift_id, stars, price, status="delivered", error=None):
        cur = await self.conn.execute(
            "INSERT INTO orders (user_id, recipient_id, gift_id, gift_stars, price, status, error) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, recipient_id, gift_id, stars, price, status, error),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def user_orders(self, uid: int, limit: int = 10):
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit)
        )
        return await cur.fetchall()

    async def stats(self):
        q = lambda sql: self.conn.execute(sql)  # noqa: E731
        users = await (await q("SELECT COUNT(*) c, COALESCE(SUM(balance),0) b FROM users")).fetchone()
        tops = await (await q(
            "SELECT method, COUNT(*) c, COALESCE(SUM(amount),0) s FROM topups WHERE status='paid' GROUP BY method"
        )).fetchall()
        orders = await (await q(
            "SELECT COUNT(*) c, COALESCE(SUM(price),0) s, COALESCE(SUM(gift_stars),0) st "
            "FROM orders WHERE status='delivered'"
        )).fetchone()
        return users, tops, orders


db = DB()
