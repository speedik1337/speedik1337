import asyncio
import logging

from aiogram import Bot, Dispatcher

from .config import cfg
from .crypto import crypto
from .db import db
from .handlers import admin, payments, shop


async def main():
    logging.basicConfig(level=logging.INFO)
    await db.init(cfg.db_path)
    bot = Bot(cfg.bot_token)
    dp = Dispatcher()
    dp.include_routers(admin.router, payments.router, shop.router)
    if crypto.enabled:
        asyncio.create_task(payments.crypto_poller(bot))
    if not (cfg.card_provider_token or crypto.enabled):
        logging.warning("Не настроен ни один способ оплаты (CARD_PROVIDER_TOKEN / CRYPTO_PAY_TOKEN)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
