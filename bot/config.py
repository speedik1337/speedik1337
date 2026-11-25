import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    crypto_token: str
    crypto_url: str
    admin_ids: frozenset[int]
    star_price_usd: float
    markup: float
    db_path: str


def load() -> Config:
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        crypto_token=os.environ["CRYPTO_PAY_TOKEN"],
        crypto_url=os.getenv("CRYPTO_PAY_URL", "https://pay.crypt.bot/api").rstrip("/"),
        admin_ids=frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()),
        star_price_usd=float(os.getenv("STAR_PRICE_USD", "0.02")),
        markup=float(os.getenv("MARKUP_PERCENT", "20")) / 100,
        db_path=os.getenv("DB_PATH", "bot.db"),
    )
