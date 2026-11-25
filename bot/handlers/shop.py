import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M
from aiogram.types import Message

from .. import catalog
from ..catalog import fmt
from ..config import cfg
from ..db import db
from ..keyboards import MENU_GIFTS, MENU_HELP, MENU_ORDERS, MENU_TEXTS, main_menu

router = Router()
PAGE = 9


class Buy(StatesGroup):
    recipient = State()
    text = State()


@router.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(m.from_user.id)
    await m.answer(
        "👋 Добро пожаловать в магазин Telegram-подарков!\n\n"
        "1. Пополните баланс картой Humo / Uzcard или криптой\n"
        "2. Выберите подарок\n"
        "3. Подарок мгновенно придёт вам или другу",
        reply_markup=main_menu,
    )


@router.message(F.text == MENU_HELP)
async def help_(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(
        "❓ <b>Как это работает</b>\n\n"
        "• Подарки отправляются от имени бота прямо в профиль получателя.\n"
        "• Получателю нужно хотя бы раз написать этому боту (/start).\n"
        "• Узнать свой ID можно у @userinfobot.\n"
        "• Если подарок не дошёл — деньги автоматически вернутся на баланс.",
        parse_mode="HTML",
    )


@router.message(F.text == MENU_ORDERS)
async def orders(m: Message, state: FSMContext):
    await state.clear()
    rows = await db.user_orders(m.from_user.id)
    if not rows:
        return await m.answer("У вас пока нет заказов.")
    icon = {"delivered": "✅", "refunded": "↩️"}
    lines = [f"{icon.get(r['status'], '•')} #{r['id']} · {r['gift_stars']}⭐ · {fmt(r['price'])} → {r['recipient_id']}"
             for r in rows]
    await m.answer("📦 Последние заказы:\n\n" + "\n".join(lines))


# ---------- Каталог ----------

async def tiers_kb(bot: Bot) -> M:
    rows = [[B(text=f"{title} · {n}", callback_data=f"cat:{key}:0")]
            for key, title, n in await catalog.tiers_available(bot)]
    rows.append([B(text="📋 Все подарки", callback_data="cat:all:0")])
    return M(inline_keyboard=rows)


@router.message(F.text == MENU_GIFTS)
@router.message(Command("shop"))
async def shop(m: Message, bot: Bot, state: FSMContext):
    await state.clear()
    await m.answer("🎁 Выберите категорию:", reply_markup=await tiers_kb(bot))


@router.callback_query(F.data == "cats")
async def shop_back(c: CallbackQuery, bot: Bot):
    await c.message.edit_text("🎁 Выберите категорию:", reply_markup=await tiers_kb(bot))
    await c.answer()


@router.callback_query(F.data.startswith("cat:"))
async def show_tier(c: CallbackQuery, bot: Bot):
    _, tier, page = c.data.split(":")
    page = int(page)
    items = await catalog.gifts(bot) if tier == "all" else await catalog.by_tier(bot, tier)
    chunk = items[page * PAGE:(page + 1) * PAGE]
    if not chunk:
        return await c.answer("Здесь пока пусто", show_alert=True)

    rows, row = [], []
    for g in chunk:
        row.append(B(text=f"{g.sticker.emoji or '🎁'} {g.star_count}⭐", callback_data=f"g:{g.id}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(B(text="◀️", callback_data=f"cat:{tier}:{page - 1}"))
    pages = (len(items) - 1) // PAGE + 1
    nav.append(B(text=f"{page + 1}/{pages}", callback_data="noop"))
    if (page + 1) * PAGE < len(items):
        nav.append(B(text="▶️", callback_data=f"cat:{tier}:{page + 1}"))
    rows.append(nav)
    rows.append([B(text="« Категории", callback_data="cats")])

    lo, hi = catalog.price(chunk[0].star_count), catalog.price(chunk[-1].star_count)
    await c.message.edit_text(
        f"Подарков: {len(items)}. Цены на странице: {fmt(lo)} – {fmt(hi)}\nНажмите на подарок:",
        reply_markup=M(inline_keyboard=rows),
    )
    await c.answer()


@router.callback_query(F.data == "noop")
async def noop(c: CallbackQuery):
    await c.answer()


@router.callback_query(F.data.startswith("g:"))
async def gift_card(c: CallbackQuery, bot: Bot):
    g = await catalog.find(bot, c.data[2:])
    if not g:
        return await c.answer("Подарок больше недоступен", show_alert=True)
    bal = await db.balance(c.from_user.id)
    p = catalog.price(g.star_count)
    info = [f"{g.sticker.emoji or '🎁'} <b>Подарок за {g.star_count}⭐</b>", f"Цена: <b>{fmt(p)}</b>"]
    if g.total_count:
        info.append(f"🔥 Лимитированный: осталось {g.remaining_count} из {g.total_count}")
    if g.is_premium:
        info.append("⭐ Только для получателей с Telegram Premium")
    info.append(f"\nВаш баланс: {fmt(bal)}")
    await bot.send_sticker(c.from_user.id, g.sticker.file_id)
    await c.message.answer(
        "\n".join(info),
        parse_mode="HTML",
        reply_markup=M(inline_keyboard=[
            [B(text=f"🛒 Купить за {fmt(p)}", callback_data=f"buy:{g.id}")],
            [B(text="« К каталогу", callback_data="cats_new")],
        ]),
    )
    await c.answer()


@router.callback_query(F.data == "cats_new")
async def cats_new(c: CallbackQuery, bot: Bot):
    await c.message.answer("🎁 Выберите категорию:", reply_markup=await tiers_kb(bot))
    await c.answer()


# ---------- Покупка ----------

@router.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery, bot: Bot, state: FSMContext):
    g = await catalog.find(bot, c.data[4:])
    if not g:
        return await c.answer("Подарок больше недоступен", show_alert=True)
    p = catalog.price(g.star_count)
    bal = await db.balance(c.from_user.id)
    if bal < p:
        await c.message.answer(
            f"Недостаточно средств: нужно {fmt(p)}, на балансе {fmt(bal)}.",
            reply_markup=M(inline_keyboard=[[B(text="💰 Пополнить", callback_data="topup")]]),
        )
        return await c.answer()
    await state.set_state(Buy.recipient)
    await state.update_data(gift_id=g.id, stars=g.star_count, price=p)
    await c.message.answer(
        "Кому отправить подарок?\nПришлите числовой Telegram ID получателя или нажмите «Себе».",
        reply_markup=M(inline_keyboard=[[B(text="🙋 Себе", callback_data="rcpt:self")],
                                        [B(text="Отмена", callback_data="rcpt:cancel")]]),
    )
    await c.answer()


@router.callback_query(Buy.recipient, F.data == "rcpt:cancel")
async def cancel(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.edit_text("Покупка отменена.")
    await c.answer()


async def ask_text(msg: Message, state: FSMContext, recipient_id: int):
    await state.update_data(recipient_id=recipient_id)
    await state.set_state(Buy.text)
    await msg.answer(
        "Добавить подпись к подарку (до 128 символов)? Напишите текст или нажмите «Без подписи».",
        reply_markup=M(inline_keyboard=[[B(text="Без подписи", callback_data="txt:none")]]),
    )


@router.callback_query(Buy.recipient, F.data == "rcpt:self")
async def rcpt_self(c: CallbackQuery, state: FSMContext):
    await ask_text(c.message, state, c.from_user.id)
    await c.answer()


@router.message(Buy.recipient, F.text.regexp(r"^\d{5,15}$"))
async def rcpt_id(m: Message, state: FSMContext):
    await ask_text(m, state, int(m.text))


@router.message(Buy.recipient, ~F.text.in_(MENU_TEXTS))
async def rcpt_bad(m: Message):
    await m.answer("Нужен числовой ID (только цифры). Узнать ID можно у @userinfobot.")


@router.callback_query(Buy.text, F.data == "txt:none")
async def txt_none(c: CallbackQuery, bot: Bot, state: FSMContext):
    await c.answer()
    await finish(c.message, c.from_user.id, bot, state, None)


@router.message(Buy.text, F.text, ~F.text.in_(MENU_TEXTS))
async def txt(m: Message, bot: Bot, state: FSMContext):
    await finish(m, m.from_user.id, bot, state, m.text[:128])


async def finish(msg: Message, uid: int, bot: Bot, state: FSMContext, text: str | None):
    d = await state.get_data()
    await state.clear()
    if not await db.charge(uid, d["price"]):
        return await msg.answer("Недостаточно средств на балансе.")
    try:
        await bot.send_gift(user_id=d["recipient_id"], gift_id=d["gift_id"], text=text)
    except Exception as e:
        logging.exception("send_gift failed")
        await db.add_balance(uid, d["price"])  # возврат
        oid = await db.create_order(uid, d["recipient_id"], d["gift_id"], d["stars"], d["price"], "refunded", str(e))
        await msg.answer(
            f"⚠️ Не удалось отправить подарок (заказ #{oid}). {fmt(d['price'])} возвращены на баланс.\n"
            "Проверьте, что получатель запускал бота, и попробуйте снова."
        )
        for a in cfg.admin_ids:
            await bot.send_message(a, f"❗ Заказ #{oid} не доставлен: {e}")
        return
    oid = await db.create_order(uid, d["recipient_id"], d["gift_id"], d["stars"], d["price"])
    await msg.answer(
        f"✅ Подарок отправлен! Заказ #{oid}\nОстаток на балансе: {fmt(await db.balance(uid))}",
        reply_markup=main_menu,
    )


