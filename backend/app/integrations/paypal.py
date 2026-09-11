import base64

import httpx

from app.core.config import settings


async def _get_access_token():
    auth = base64.b64encode(
        f"{settings.paypal_client_id}:{settings.paypal_client_secret}".encode()
    ).decode()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.paypal_base_url}/v1/oauth2/token",
            headers={"Authorization": f"Basic {auth}"},
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def send_payout(amount: float, currency: str, receiver: str) -> str:
    token = await _get_access_token()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.paypal_base_url}/v1/payments/payouts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "sender_batch_header": {"sender_batch_id": "rosulo-batch"},
                "items": [
                    {
                        "recipient_type": "EMAIL",
                        "amount": {"value": f"{amount:.2f}", "currency": currency},
                        "receiver": receiver,
                    }
                ],
            },
        )
        resp.raise_for_status()
        return resp.json().get("batch_header", {}).get("payout_batch_id", "")
