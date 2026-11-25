import aiohttp


class CryptoPay:
    def __init__(self, url: str, token: str):
        self.url, self.token = url, token

    async def _call(self, method: str, params: dict):
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{self.url}/{method}",
                params=params,
                headers={"Crypto-Pay-API-Token": self.token},
            ) as r:
                data = await r.json()
        if not data.get("ok"):
            raise RuntimeError(f"CryptoPay {method}: {data.get('error')}")
        return data["result"]

    async def create_invoice(self, amount_usd: float, description: str, payload: str, ttl: int = 1800):
        return await self._call(
            "createInvoice",
            {
                "currency_type": "fiat",
                "fiat": "USD",
                "amount": f"{amount_usd:.2f}",
                "description": description[:1024],
                "payload": payload,
                "expires_in": ttl,
            },
        )

    async def get_invoice_status(self, invoice_id: int) -> str:
        res = await self._call("getInvoices", {"invoice_ids": str(invoice_id)})
        items = res.get("items", [])
        return items[0]["status"] if items else "expired"  # active | paid | expired
