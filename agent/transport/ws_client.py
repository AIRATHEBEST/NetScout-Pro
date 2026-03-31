"""
WebSocket client that connects the agent to the backend.
Handles reconnection, authentication, and message framing.
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    WebSocketException,
)

from config import BACKEND_WS_URL, AGENT_TOKEN, AGENT_ID

logger = logging.getLogger(__name__)

RECONNECT_DELAY_MIN = 2    # seconds
RECONNECT_DELAY_MAX = 60   # seconds
HEARTBEAT_INTERVAL = 30    # seconds


class AgentWebSocketClient:
    def __init__(self):
        self._ws = None
        self._connected = False
        self._reconnect_delay = RECONNECT_DELAY_MIN
        self._send_queue: asyncio.Queue = asyncio.Queue()
        self._on_command_callback: Optional[Callable] = None

    def on_command(self, callback: Callable):
        """Register callback for incoming commands from backend."""
        self._on_command_callback = callback

    async def connect_and_run(self):
        """Main loop: connect, authenticate, send/receive until shutdown."""
        while True:
            try:
                logger.info(f"Connecting to backend at {BACKEND_WS_URL}")
                async with websockets.connect(
                    BACKEND_WS_URL,
                    extra_headers={"X-Agent-Token": AGENT_TOKEN},
                    ping_interval=HEARTBEAT_INTERVAL,
                    ping_timeout=15,
                    close_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_delay = RECONNECT_DELAY_MIN
                    logger.info("Connected to backend WebSocket")

                    # Authenticate
                    await self._send_raw(ws, {
                        "type": "auth",
                        "agent_id": AGENT_ID,
                        "token": AGENT_TOKEN,
                        "timestamp": time.time(),
                    })

                    # Run sender and receiver concurrently
                    await asyncio.gather(
                        self._sender_loop(ws),
                        self._receiver_loop(ws),
                    )

            except (ConnectionClosed, ConnectionClosedError) as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
            except OSError as e:
                logger.error(f"Connection failed: {e}")
            except Exception as e:
                logger.error(f"Unexpected WebSocket error: {e}")
            finally:
                self._ws = None
                self._connected = False

            logger.info(f"Reconnecting in {self._reconnect_delay}s...")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(
                self._reconnect_delay * 2, RECONNECT_DELAY_MAX
            )

    async def _sender_loop(self, ws):
        """Drain the send queue and send messages."""
        while True:
            message = await self._send_queue.get()
            try:
                await ws.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Send error: {e}")
                # Re-queue the message for after reconnect
                await self._send_queue.put(message)
                raise  # Trigger reconnect
            finally:
                self._send_queue.task_done()

    async def _receiver_loop(self, ws):
        """Receive messages from backend and handle commands."""
        async for raw in ws:
            try:
                message = json.loads(raw)
                await self._handle_incoming(message)
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON message: {raw[:100]}")
            except Exception as e:
                logger.error(f"Error handling incoming message: {e}")

    async def _handle_incoming(self, message: dict):
        """Handle commands from the backend."""
        msg_type = message.get("type")

        if msg_type == "auth_ok":
            logger.info("Agent authenticated with backend")

        elif msg_type == "auth_error":
            logger.error(f"Authentication failed: {message.get('error')}")

        elif msg_type == "command":
            logger.info(f"Received command: {message.get('command')}")
            if self._on_command_callback:
                await self._on_command_callback(message)

        elif msg_type == "pong":
            pass  # heartbeat response

        else:
            logger.debug(f"Unhandled message type: {msg_type}")

    async def _send_raw(self, ws, data: dict):
        """Send a message directly (bypass queue)."""
        await ws.send(json.dumps(data))

    async def send_scan_result(self, scan_data: dict):
        """Queue a scan result to be sent to the backend."""
        await self._send_queue.put({
            "type": "scan_result",
            "agent_id": AGENT_ID,
            "timestamp": time.time(),
            "data": scan_data,
        })

    async def send_device_event(self, event_type: str, device: dict):
        """
        Send a device event (joined/left/updated).
        event_type: 'device_joined' | 'device_left' | 'device_updated'
        """
        await self._send_queue.put({
            "type": event_type,
            "agent_id": AGENT_ID,
            "timestamp": time.time(),
            "device": device,
        })

    async def send_alert(self, alert: dict):
        """Send a security alert to the backend."""
        await self._send_queue.put({
            "type": "alert",
            "agent_id": AGENT_ID,
            "timestamp": time.time(),
            "alert": alert,
        })

    async def send_heartbeat(self):
        """Send a status heartbeat."""
        await self._send_queue.put({
            "type": "heartbeat",
            "agent_id": AGENT_ID,
            "timestamp": time.time(),
            "status": "running",
        })

    @property
    def is_connected(self) -> bool:
        return self._connected
