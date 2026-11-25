# Бот-магазин Telegram-подарков

Покупатель выбирает подарок, платит в крипте через CryptoBot, бот отправляет подарок (`sendGift`) со своего баланса Stars.

## Запуск
1. `pip install -r requirements.txt`
2. `cp .env.example .env` и заполните токены (бот — у @BotFather, платёжка — @CryptoBot → Crypto Pay).
3. **Пополните баланс Stars у бота**, иначе подарки не отправятся.
4. `python -m bot.main`

Команды: `/shop` — каталог, `/stats` — статистика (админы).
Цена = цена в Stars × `STAR_PRICE_USD` × (1 + `MARKUP_PERCENT`%).
