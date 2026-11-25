import asyncio
import logging
import math

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import config
from .crypto import CryptoPay
from .db import DB

cfg = config.load()
db = DB(cfg.db_path)
crypto = CryptoPay(cfg.crypto_url, cfg.crypto_token)
router = Router()


class Buy(StatesGroup):
    recipient = State()


def price_usd(stars: int) -> float:
    return math.ceil(stars * cfg.star_price_usd * (1 + cfg.markup) * 100) / 100


async def catalog(bot: Bot):
    gifts = (await bot.get_available_gifts()).gifts
    # только доступные (не распроданные лимитки)
    return [g for g in gifts if g.remaining_count is None or g.remaining_count > 0]


@router.message(CommandStart())
@router.message(Command("shop"))
async def shop(m: Message, bot: Bot, state: FSMContext):
    await state.clear()
    gifts = await catalog(bot)
    kb = InlineKeyboardBuilder()
    for g in sorted(gifts, key=lambda g: g.star_count):
        kb.button(text=f"{g.sticker.emoji or '🎁'} ${price_usd(g.star_count):.2f}", callback_data=f"g:{g.id}")
    kb.adjust(3)
    await m.answer("🎁 Выберите подарок:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("g:"))
async def pick(c: CallbackQuery, state: FSMContext, bot: Bot):
    gid = c.data[2:]
    gift = next((g for g in await catalog(bot) if g.id == gid), None)
    if not gift:
        return await c.answer("Подарок недоступен", show_alert=True)
    await state.update_data(gift_id=gid, stars=gift.star_count)
    await state.set_state(Buy.recipient)
    await c.message.answer(
        "Кому отправить? Пришлите числовой Telegram ID получателя "
        "(получатель должен хоть раз написать боту) или нажмите «Себе».",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Себе", callback_data="self")]]
        ),
    )
    await c.answer()


async def make_order(msg: Message, state: FSMContext, user_id: int, recipient_id: int):
    d = await state.get_data()
    await state.clear()
    usd = price_usd(d["stars"])
    oid = await db.create_order(user_id, recipient_id, d["gift_id"], d["stars"], usd)
    inv = await crypto.create_invoice(usd, f"Telegram-подарок, заказ #{oid}", str(oid))
    await db.set_invoice(oid, inv["invoice_id"], inv["bot_invoice_url"])
    await msg.answer(
        f"Заказ #{oid}: ${usd:.2f}\nОплатите в течение 30 минут — подарок уйдёт автоматически.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", url=inv["bot_invoice_url"])]]
        ),
    )


@router.callback_query(Buy.recipient, F.data == "self")
async def to_self(c: CallbackQuery, state: FSMContext):
    await make_order(c.message, state, c.from_user.id, c.from_user.id)
    await c.answer()


@router.message(Buy.recipient, F.text.regexp(r"^\d{5,15}$"))
async def to_other(m: Message, state: FSMContext):
    await make_order(m, state, m.from_user.id, int(m.text))


@router.message(Buy.recipient)
async def bad_recipient(m: Message):
    await m.answer("Нужен числовой ID (только цифры).")


@router.message(Command("stats"), F.from_user.id.in_(cfg.admin_ids))
async def stats(m: Message, bot: Bot):
    rows = await db.stats()
    me = await bot.get_my_star_balance()
    lines = [f"{r['status']}: {r['c']} шт. / ${r['s']:.2f}" for r in rows] or ["Заказов нет"]
    await m.answer("\n".join(lines) + f"\n\n⭐ Баланс бота: {me.amount}")


async def deliver(bot: Bot, o):
    if not await db.claim_paid(o["id"]):
        return
    try:
        await bot.send_gift(user_id=o["recipient_id"], gift_id=o["gift_id"], text="С подарком! 🎁")
        await db.set_status(o["id"], "delivered")
        await bot.send_message(o["user_id"], f"✅ Заказ #{o['id']} доставлен!")
    except Exception as e:  # чаще всего: мало Stars на балансе бота
        logging.exception("delivery failed")
        await db.set_status(o["id"], "failed", str(e))
        await bot.send_message(o["user_id"], f"⚠️ Заказ #{o['id']}: не удалось отправить, с вами свяжется админ.")
        for a in cfg.admin_ids:
            await bot.send_message(a, f"❗ Заказ #{o['id']} оплачен, но не доставлен: {e}")


async def poller(bot: Bot):
    while True:
        try:
            for o in await db.pending():
                status = await crypto.get_invoice_status(o["invoice_id"])
                if status == "paid":
                    await deliver(bot, o)
                elif status == "expired":
                    await db.set_status(o["id"], "expired")
        except Exception:
            logging.exception("poller error")
        await asyncio.sleep(10)


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init()
    bot = Bot(cfg.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    asyncio.create_task(poller(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
