"""
SOC Triager — AWS CloudTrail Connector.

Polls an SQS queue backed by EventBridge → CloudTrail → S3 → SQS notification,
downloads the CloudTrail log file from S3, and publishes each event to the
raw.cloudtrail Redpanda topic.

Deployment: Run as a standalone process or Kubernetes Deployment (1 replica).
Environment variables:
    SQS_QUEUE_URL          — SQS queue URL receiving S3 event notifications
    AWS_REGION             — AWS region (default: us-east-1)
    KAFKA_BOOTSTRAP_SERVERS — Redpanda bootstrap servers
    LOG_LEVEL              — Log level (default: INFO)
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os

import boto3
import structlog
from aiokafka import AIOKafkaProducer

log = structlog.get_logger()

SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
TOPIC = "raw.cloudtrail"
POLL_WAIT_SECONDS = 20  # SQS long-polling wait time


async def _publish_events(producer: AIOKafkaProducer, events: list[dict]) -> None:
    for event in events:
        value = json.dumps(event).encode("utf-8")
        await producer.send_and_wait(TOPIC, value=value)


def _download_cloudtrail_log(bucket: str, key: str) -> list[dict]:
    """Download and parse a CloudTrail log file from S3."""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read()

    if key.endswith(".gz"):
        body = gzip.decompress(body)

    log_data = json.loads(body)
    return log_data.get("Records", [])


async def run_connector() -> None:
    """Main loop: poll SQS → download S3 → publish to Redpanda."""
    sqs = boto3.client("sqs", region_name=AWS_REGION)

    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()
    log.info("cloudtrail_connector_started", queue=SQS_QUEUE_URL, topic=TOPIC)

    try:
        while True:
            # Long-poll SQS for up to 20 seconds
            response = sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=POLL_WAIT_SECONDS,
                AttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            for message in messages:
                try:
                    body = json.loads(message["Body"])
                    # SNS wrapper if EventBridge → SNS → SQS
                    if "Message" in body:
                        body = json.loads(body["Message"])

                    # S3 event notification format
                    for record in body.get("Records", []):
                        bucket = record["s3"]["bucket"]["name"]
                        key = record["s3"]["object"]["key"]

                        events = _download_cloudtrail_log(bucket, key)
                        await _publish_events(producer, events)

                        log.info(
                            "cloudtrail_batch_published",
                            bucket=bucket,
                            key=key,
                            count=len(events),
                        )

                    # Delete message from queue after successful processing
                    sqs.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message["ReceiptHandle"],
                    )

                except Exception as exc:
                    log.error("cloudtrail_message_error", error=str(exc))
                    # Don't delete — let SQS retry after visibility timeout

    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run_connector())
