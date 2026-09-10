import json

import boto3

from app.core.config import settings


def publish_payout(payout_id: str):
    if not settings.sqs_queue_url:
        return
    sqs = boto3.client("sqs")
    sqs.send_message(
        QueueUrl=settings.sqs_queue_url,
        MessageBody=json.dumps({"type": "payout", "payout_id": payout_id}),
    )
