import aiohttp

from .config import cfg


class CryptoPay:
    """Минимальный клиент Crypto Pay API (@CryptoBot)."""

    def __init__(self, url: str, token: str):
        self.url, self.token = url, token

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    async def _call(self, method: str, params: dict):
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{self.url}/{method}", params=params, headers={"Crypto-Pay-API-Token": self.token}
            ) as r:
                data = await r.json()
        if not data.get("ok"):
            raise RuntimeError(f"CryptoPay {method}: {data.get('error')}")
        return data["result"]

    async def create_invoice(self, amount_uzs: int, description: str, payload: str, ttl: int = 1800):
        # Счёт выставляется в сумах; покупатель платит в USDT/TON/BTC и т.д. по курсу CryptoBot
        return await self._call(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": "UZS",
                "amount": str(amount_uzs),
                "description": description[:1024],
                "payload": payload,
                "expires_in": ttl,
            },
        )

    async def statuses(self, invoice_ids: list[str]) -> dict[str, str]:
        res = await self._call("getInvoices", {"invoice_ids": ",".join(invoice_ids)})
        return {str(i["invoice_id"]): i["status"] for i in res.get("items", [])}  # active|paid|expired


crypto = CryptoPay(cfg.crypto_url, cfg.crypto_token)
