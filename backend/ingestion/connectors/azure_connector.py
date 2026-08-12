"""
SOC Triager — Azure Activity Log / Event Hub Connector.

Consumes events from Azure Event Hub (backed by Activity Log diagnostic settings),
normalises them to ECS-compatible JSON, and publishes to the raw.cloudtrail
Redpanda topic (shares the CloudTrail topic since both are cloud audit logs).

Environment variables:
    AZURE_EVENT_HUB_CONN_STR   — Event Hub namespace connection string
    AZURE_EVENT_HUB_NAME       — Event Hub name (default: insights-activity-logs)
    AZURE_CONSUMER_GROUP       — Consumer group (default: soc-triager)
    AZURE_CHECKPOINT_STORE_URL — Azure Blob SAS URL for checkpoint storage
    KAFKA_BOOTSTRAP_SERVERS     — Redpanda bootstrap servers

Deploy as a single Kubernetes Deployment (1 replica per Event Hub partition group).
"""

from __future__ import annotations

import asyncio
import json
import os

import structlog
from aiokafka import AIOKafkaProducer
from azure.eventhub.aio import EventHubConsumerClient
from azure.eventhub.extensions.checkpointstoreblobaio import BlobCheckpointStore

log = structlog.get_logger()

EVENT_HUB_CONN_STR = os.environ["AZURE_EVENT_HUB_CONN_STR"]
EVENT_HUB_NAME = os.environ.get("AZURE_EVENT_HUB_NAME", "insights-activity-logs")
CONSUMER_GROUP = os.environ.get("AZURE_CONSUMER_GROUP", "soc-triager")
CHECKPOINT_STORE_URL = os.environ.get("AZURE_CHECKPOINT_STORE_URL", "")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
TOPIC = "raw.cloudtrail"  # Shared cloud-audit topic


def _normalise_azure_event(record: dict) -> dict:
    """
    Lightly normalise an Azure Activity Log record to match CloudTrail shape
    so the downstream normalizer can handle both with the same code path.
    """
    return {
        "source": "azure_activity_log",
        "eventTime": record.get("time", ""),
        "eventSource": record.get("resourceProvider", "azure"),
        "eventName": record.get("operationName", {}).get("value", ""),
        "awsRegion": record.get("location", ""),
        "userIdentity": {
            "type": "AzureUser",
            "principalId": record.get("caller", ""),
        },
        "requestParameters": record.get("properties", {}),
        "responseElements": {
            "httpStatusCode": record.get("httpRequest", {}).get("clientRequestId", ""),
        },
        "sourceIPAddress": record.get("httpRequest", {}).get("clientIpAddress", ""),
        "_raw": record,
    }


_producer: AIOKafkaProducer | None = None


async def _on_event(partition_context, event) -> None:
    """Callback for each received Event Hub event."""
    global _producer
    try:
        body = event.body_as_json()
        # Azure Activity Log wraps records in {"records": [...]}
        records = body.get("records", [body])

        for record in records:
            normalised = _normalise_azure_event(record)
            value = json.dumps(normalised).encode("utf-8")
            if _producer:
                await _producer.send_and_wait(TOPIC, value=value)

        await partition_context.update_checkpoint(event)
        log.info("azure_events_published", count=len(records), partition=partition_context.partition_id)

    except Exception as exc:
        log.error("azure_event_error", error=str(exc))


async def run_connector() -> None:
    """Start Azure Event Hub consumer and publish to Redpanda."""
    global _producer

    _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await _producer.start()

    # Use Blob storage for checkpoint durability across restarts
    checkpoint_store = (
        BlobCheckpointStore.from_connection_string(CHECKPOINT_STORE_URL, "soc-checkpoints")
        if CHECKPOINT_STORE_URL
        else None
    )

    client = EventHubConsumerClient.from_connection_string(
        EVENT_HUB_CONN_STR,
        consumer_group=CONSUMER_GROUP,
        eventhub_name=EVENT_HUB_NAME,
        checkpoint_store=checkpoint_store,
    )

    log.info(
        "azure_connector_started",
        event_hub=EVENT_HUB_NAME,
        consumer_group=CONSUMER_GROUP,
        topic=TOPIC,
    )

    try:
        async with client:
            await client.receive(
                on_event=_on_event,
                starting_position="-1",  # Start from earliest unprocessed
            )
    finally:
        if _producer:
            await _producer.stop()


if __name__ == "__main__":
    asyncio.run(run_connector())
