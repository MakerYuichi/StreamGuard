"""
StreamGuard - WebSocket Server
Broadcasts alerts to any connected frontend client, per the agreed
message format: {"type": "alert", "data": {...}}

Runs in its own thread so the Kafka consumer loop isn't blocked.
"""

import asyncio
import json
import threading

import websockets

from streamguard.consumer import config

_connected_clients = set()
_loop = None


async def _handler(websocket):
    _connected_clients.add(websocket)
    print(f"[websocket] client connected ({len(_connected_clients)} total)")
    try:
        async for _ in websocket:
            pass  # we don't expect incoming messages from the frontend
    finally:
        _connected_clients.remove(websocket)
        print(f"[websocket] client disconnected ({len(_connected_clients)} total)")


async def _broadcast_async(message: dict):
    if _connected_clients:
        payload = json.dumps(message)
        await asyncio.gather(
            *[client.send(payload) for client in _connected_clients],
            return_exceptions=True,
        )


def broadcast(alert: dict):
    """Call this from the (synchronous) consumer loop."""
    message = {"type": "alert", "data": alert}
    if _loop is not None:
        asyncio.run_coroutine_threadsafe(_broadcast_async(message), _loop)


def _run_server():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    async def main():
        async with websockets.serve(_handler, config.WEBSOCKET_HOST, config.WEBSOCKET_PORT):
            print(f"[websocket] listening on ws://{config.WEBSOCKET_HOST}:{config.WEBSOCKET_PORT}")
            await asyncio.Future()  # run forever

    _loop.run_until_complete(main())


def start_in_background():
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()