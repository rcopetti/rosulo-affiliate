import json
import time

import boto3

from app.core.config import settings
from app.db.session import async_session
from app.queue.handlers import handle_payout


def run_worker():
    if not settings.sqs_queue_url:
        print("SQS_QUEUE_URL not configured, using local polling loop")
        return
    sqs = boto3.client("sqs")
    while True:
        resp = sqs.receive_message(
            QueueUrl=settings.sqs_queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
        )
        messages = resp.get("Messages", [])
        for msg in messages:
            body = json.loads(msg["Body"])
            if body.get("type") == "payout":
                _process(body["payout_id"])
            sqs.delete_message(
                QueueUrl=settings.sqs_queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )


def _process(payout_id: str):
    import asyncio

    asyncio.run(_async_process(payout_id))


async def _async_process(payout_id: str):
    async with async_session() as db:
        await handle_payout(db, payout_id)


if __name__ == "__main__":
    run_worker()
