import math
import time

from aiogram import Bot
from aiogram.types import Gift

from .config import cfg

# Ценовые категории (в Stars): (ключ, название, min, max)
TIERS = [
    ("cheap", "💚 Недорогие (до 50⭐)", 0, 50),
    ("mid", "💙 Средние (51–250⭐)", 51, 250),
    ("high", "💜 Дорогие (251–1000⭐)", 251, 1000),
    ("top", "💎 Премиум (1000⭐+)", 1001, 10**9),
]
LIMITED = ("limited", "🔥 Лимитированные")

_cache: tuple[float, list[Gift]] = (0.0, [])


def price(stars: int) -> int:
    """Цена в сумах с наценкой, округлённая вверх до 100 сум."""
    raw = stars * cfg.star_price_uzs * (1 + cfg.markup)
    return int(math.ceil(raw / 100) * 100)


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " сум"


async def gifts(bot: Bot) -> list[Gift]:
    global _cache
    if time.time() - _cache[0] > 300:
        items = (await bot.get_available_gifts()).gifts
        items = [g for g in items if g.remaining_count is None or g.remaining_count > 0]
        _cache = (time.time(), sorted(items, key=lambda g: g.star_count))
    return _cache[1]


async def by_tier(bot: Bot, tier: str) -> list[Gift]:
    items = await gifts(bot)
    if tier == LIMITED[0]:
        return [g for g in items if g.total_count]
    _, _, lo, hi = next(t for t in TIERS if t[0] == tier)
    return [g for g in items if lo <= g.star_count <= hi]


async def find(bot: Bot, gift_id: str) -> Gift | None:
    return next((g for g in await gifts(bot) if g.id == gift_id), None)


async def tiers_available(bot: Bot) -> list[tuple[str, str, int]]:
    """Категории, в которых реально есть подарки: (ключ, название, кол-во)."""
    out = []
    for key, title, *_ in TIERS:
        n = len(await by_tier(bot, key))
        if n:
            out.append((key, title, n))
    n = len(await by_tier(bot, LIMITED[0]))
    if n:
        out.append((LIMITED[0], LIMITED[1], n))
    return out
