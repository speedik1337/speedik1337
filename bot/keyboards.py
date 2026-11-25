from aiogram.types import InlineKeyboardButton as B
from aiogram.types import InlineKeyboardMarkup as M
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from .config import cfg

MENU_GIFTS = "🎁 Подарки"
MENU_BALANCE = "💰 Баланс"
MENU_ORDERS = "📦 Мои заказы"
MENU_HELP = "❓ Помощь"
MENU_TEXTS = {MENU_GIFTS, MENU_BALANCE, MENU_ORDERS, MENU_HELP}

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=MENU_GIFTS), KeyboardButton(text=MENU_BALANCE)],
        [KeyboardButton(text=MENU_ORDERS), KeyboardButton(text=MENU_HELP)],
    ],
    resize_keyboard=True,
)

TOPUP_PRESETS = [10_000, 25_000, 50_000, 100_000, 250_000, 500_000]


def topup_amounts() -> M:
    rows, row = [], []
    for a in TOPUP_PRESETS:
        row.append(B(text=f"{a:,}".replace(",", " "), callback_data=f"top:{a}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([B(text="✏️ Своя сумма", callback_data="top:custom")])
    return M(inline_keyboard=rows)


def topup_methods(amount: int) -> M:
    rows = []
    if cfg.card_provider_token:
        rows.append([B(text="💳 Картой Humo / Uzcard", callback_data=f"pay:card:{amount}")])
    if cfg.crypto_token:
        rows.append([B(text="🪙 Криптовалютой (USDT, TON, BTC…)", callback_data=f"pay:crypto:{amount}")])
    rows.append([B(text="« Назад", callback_data="balance")])
    return M(inline_keyboard=rows)
