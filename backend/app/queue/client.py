"""Outbound payout dispatch was retired.

``publish_payout`` was removed so no application path can enqueue a new
provider transfer. The SQS worker (``app.queue.worker``) remains only to
drain stale payout messages through the no-op ``handle_payout`` handler.
"""
