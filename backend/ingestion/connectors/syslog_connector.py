"""
SOC Triager — Syslog Connector (UDP + TCP receiver).

Listens on UDP/514 and TCP/514 for incoming syslog messages (RFC 5424 / RFC 3164),
parses them into line strings, and publishes to the raw.syslog Redpanda topic.

Deploy as a DaemonSet with hostNetwork: true on nodes that need syslog collection,
or as a Deployment behind a LoadBalancer service for centralised collection.

Environment variables:
    SYSLOG_UDP_PORT        — UDP listen port (default: 514, use 5514 for non-root)
    SYSLOG_TCP_PORT        — TCP listen port (default: 514, use 5514 for non-root)
    KAFKA_BOOTSTRAP_SERVERS — Redpanda bootstrap servers
"""

from __future__ import annotations

import asyncio
import os

import structlog
from aiokafka import AIOKafkaProducer

log = structlog.get_logger()

UDP_PORT = int(os.environ.get("SYSLOG_UDP_PORT", "5514"))
TCP_PORT = int(os.environ.get("SYSLOG_TCP_PORT", "5514"))
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
TOPIC = "raw.syslog"
MAX_LINE_BYTES = 8192


class SyslogUDPProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol that queues received syslog datagrams."""

    def __init__(self, queue: asyncio.Queue) -> None:
        self._queue = queue

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            line = data.decode("utf-8", errors="replace").strip()
            if line:
                self._queue.put_nowait(line)
        except Exception as exc:
            log.warning("udp_decode_error", error=str(exc))

    def error_received(self, exc: Exception) -> None:
        log.error("udp_error", error=str(exc))


async def _handle_tcp_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    queue: asyncio.Queue,
) -> None:
    """Read syslog lines from a TCP client."""
    peer = writer.get_extra_info("peername")
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            text = line[:MAX_LINE_BYTES].decode("utf-8", errors="replace").strip()
            if text:
                await queue.put(text)
    except asyncio.IncompleteReadError:
        pass
    except Exception as exc:
        log.warning("tcp_client_error", peer=str(peer), error=str(exc))
    finally:
        writer.close()


async def _publish_worker(queue: asyncio.Queue, producer: AIOKafkaProducer) -> None:
    """Drain the queue and publish to Redpanda."""
    while True:
        line = await queue.get()
        try:
            await producer.send_and_wait(TOPIC, value=line.encode("utf-8"))
        except Exception as exc:
            log.error("syslog_publish_error", error=str(exc))
        finally:
            queue.task_done()


async def run_connector() -> None:
    """Start UDP and TCP syslog listeners and publish to Redpanda."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)

    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
    await producer.start()

    loop = asyncio.get_event_loop()

    # ── UDP listener ──────────────────────────────────────────────────────────
    transport, _ = await loop.create_datagram_endpoint(
        lambda: SyslogUDPProtocol(queue),
        local_addr=("0.0.0.0", UDP_PORT),
    )

    # ── TCP listener ──────────────────────────────────────────────────────────
    tcp_server = await asyncio.start_server(
        lambda r, w: _handle_tcp_client(r, w, queue),
        host="0.0.0.0",
        port=TCP_PORT,
    )

    log.info("syslog_connector_started", udp_port=UDP_PORT, tcp_port=TCP_PORT, topic=TOPIC)

    try:
        await asyncio.gather(
            _publish_worker(queue, producer),
            tcp_server.serve_forever(),
        )
    finally:
        transport.close()
        tcp_server.close()
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run_connector())
