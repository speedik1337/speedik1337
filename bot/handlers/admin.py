from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from ..catalog import fmt
from ..config import cfg
from ..db import db

router = Router()
router.message.filter(F.from_user.id.in_(cfg.admin_ids))


@router.message(Command("stats"))
async def stats(m: Message, bot: Bot):
    users, tops, orders = await db.stats()
    stars = (await bot.get_my_star_balance()).amount
    lines = [
        f"👥 Пользователей: {users['c']}, на балансах: {fmt(users['b'])}",
        *[f"💵 Пополнения ({t['method']}): {t['c']} шт. / {fmt(t['s'])}" for t in tops],
        f"🎁 Продано подарков: {orders['c']} на {fmt(orders['s'])} ({orders['st']}⭐)",
        f"⭐ Баланс Stars бота: {stars}" + (" ⚠️ пополните!" if stars < 500 else ""),
    ]
    await m.answer("\n".join(lines))


@router.message(Command("addbalance"))
async def addbalance(m: Message, command: CommandObject):
    """/addbalance <user_id> <сумма> — ручное начисление (можно отрицательное)."""
    try:
        uid, amount = map(int, (command.args or "").split())
    except ValueError:
        return await m.answer("Формат: /addbalance <user_id> <сумма>")
    await db.add_balance(uid, amount)
    await m.answer(f"Готово. Баланс {uid}: {fmt(await db.balance(uid))}")
