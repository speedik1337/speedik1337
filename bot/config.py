import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    crypto_token: str
    crypto_url: str
    card_provider_token: str
    star_price_uzs: float
    markup: float
    min_topup: int
    db_path: str


def load() -> Config:
    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        admin_ids=frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()),
        crypto_token=os.getenv("CRYPTO_PAY_TOKEN", ""),
        crypto_url=os.getenv("CRYPTO_PAY_URL", "https://pay.crypt.bot/api").rstrip("/"),
        card_provider_token=os.getenv("CARD_PROVIDER_TOKEN", ""),
        star_price_uzs=float(os.getenv("STAR_PRICE_UZS", "250")),
        markup=float(os.getenv("MARKUP_PERCENT", "20")) / 100,
        min_topup=int(os.getenv("MIN_TOPUP_UZS", "10000")),
        db_path=os.getenv("DB_PATH", "bot.db"),
    )


cfg = load()
