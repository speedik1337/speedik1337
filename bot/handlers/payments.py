import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from ..catalog import fmt
from ..config import cfg
from ..crypto import crypto
from ..db import db
from ..keyboards import MENU_BALANCE, MENU_TEXTS, topup_amounts, topup_methods

router = Router()
MAX_TOPUP = 10_000_000


class Topup(StatesGroup):
    amount = State()


async def balance_text(uid: int) -> str:
    return f"💰 Ваш баланс: <b>{fmt(await db.balance(uid))}</b>\n\nВыберите сумму пополнения:"


@router.message(F.text == MENU_BALANCE)
async def balance(m: Message, state: FSMContext):
    await state.clear()
    await db.ensure_user(m.from_user.id)
    await m.answer(await balance_text(m.from_user.id), parse_mode="HTML", reply_markup=topup_amounts())


@router.callback_query(F.data.in_({"balance", "topup"}))
async def balance_cb(c: CallbackQuery, state: FSMContext):
    await state.clear()
    await c.message.answer(await balance_text(c.from_user.id), parse_mode="HTML", reply_markup=topup_amounts())
    await c.answer()


@router.callback_query(F.data == "top:custom")
async def custom(c: CallbackQuery, state: FSMContext):
    await state.set_state(Topup.amount)
    await c.message.answer(f"Введите сумму в сумах (от {fmt(cfg.min_topup)}):")
    await c.answer()


@router.message(Topup.amount, ~F.text.in_(MENU_TEXTS))
async def custom_amount(m: Message, state: FSMContext):
    digits = "".join(ch for ch in (m.text or "") if ch.isdigit())
    amount = int(digits) if digits else 0
    if not cfg.min_topup <= amount <= MAX_TOPUP:
        return await m.answer(f"Сумма должна быть от {fmt(cfg.min_topup)} до {fmt(MAX_TOPUP)}.")
    await state.clear()
    await m.answer(f"Пополнение на <b>{fmt(amount)}</b>. Способ оплаты:",
                   parse_mode="HTML", reply_markup=topup_methods(amount))


@router.callback_query(F.data.regexp(r"^top:\d+$"))
async def preset(c: CallbackQuery):
    amount = int(c.data[4:])
    await c.message.edit_text(f"Пополнение на <b>{fmt(amount)}</b>. Способ оплаты:",
                              parse_mode="HTML", reply_markup=topup_methods(amount))
    await c.answer()


# ---------- Карта Humo / Uzcard (Telegram Payments: Click / Payme) ----------

@router.callback_query(F.data.startswith("pay:card:"))
async def pay_card(c: CallbackQuery, bot: Bot):
    amount = int(c.data.split(":")[2])
    tid = await db.create_topup(c.from_user.id, "card", amount)
    await bot.send_invoice(
        chat_id=c.from_user.id,
        title="Пополнение баланса",
        description=f"Пополнение на {fmt(amount)} картой Humo / Uzcard",
        payload=f"topup:{tid}",
        provider_token=cfg.card_provider_token,
        currency="UZS",
        prices=[LabeledPrice(label="Пополнение", amount=amount * 100)],  # в тийинах
    )
    await c.answer()


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    ok = False
    if q.invoice_payload.startswith("topup:"):
        t = await db.get_topup(int(q.invoice_payload[6:]))
        ok = bool(t and t["status"] == "pending" and t["amount"] * 100 == q.total_amount
                  and q.currency == "UZS" and t["user_id"] == q.from_user.id)
    await q.answer(ok=ok, error_message=None if ok else "Счёт устарел, создайте новый.")


@router.message(F.successful_payment)
async def paid(m: Message):
    sp = m.successful_payment
    tid = int(sp.invoice_payload[6:])
    if await db.complete_topup(tid, sp.telegram_payment_charge_id):
        await m.answer(f"✅ Баланс пополнен на {fmt(sp.total_amount // 100)}.\n"
                       f"Текущий баланс: {fmt(await db.balance(m.from_user.id))}")


# ---------- Крипта (CryptoBot) ----------

@router.callback_query(F.data.startswith("pay:crypto:"))
async def pay_crypto(c: CallbackQuery):
    amount = int(c.data.split(":")[2])
    tid = await db.create_topup(c.from_user.id, "crypto", amount)
    try:
        inv = await crypto.create_invoice(amount, f"Пополнение баланса на {fmt(amount)}", f"topup:{tid}")
    except Exception:
        logging.exception("crypto invoice")
        await db.expire_topup(tid)
        return await c.answer("Крипто-оплата временно недоступна", show_alert=True)
    await db.set_topup_external(tid, str(inv["invoice_id"]))
    await c.message.edit_text(
        f"🪙 Счёт на {fmt(amount)} создан. Оплатите в течение 30 минут в любой криптовалюте — "
        "баланс пополнится автоматически.",
        reply_markup=M(inline_keyboard=[[B(text="Оплатить в CryptoBot", url=inv["bot_invoice_url"])]]),
    )
    await c.answer()


async def crypto_poller(bot: Bot):
    while True:
        try:
            pending = await db.pending_crypto_topups()
            if pending:
                st = await crypto.statuses([t["external_id"] for t in pending])
                for t in pending:
                    s = st.get(t["external_id"], "expired")
                    if s == "paid" and await db.complete_topup(t["id"]):
                        await bot.send_message(
                            t["user_id"],
                            f"✅ Баланс пополнен на {fmt(t['amount'])}.\n"
                            f"Текущий баланс: {fmt(await db.balance(t['user_id']))}",
                        )
                    elif s == "expired":
                        await db.expire_topup(t["id"])
        except Exception:
            logging.exception("crypto poller")
        await asyncio.sleep(10)
