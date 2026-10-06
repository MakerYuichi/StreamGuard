"""WebSocket alert broadcaster, hosted on a dedicated asyncio thread."""
import asyncio
import json
import threading

import websockets
import config

_clients = set()
_loop = None
_ready = threading.Event()


async def _handler(websocket):
    _clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        _clients.discard(websocket)


async def _broadcast(message):
    if _clients:
        await asyncio.gather(*(client.send(json.dumps(message)) for client in tuple(_clients)),
                             return_exceptions=True)


def broadcast(alert):
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast({"type": "alert", "data": alert}), _loop)


def _serve():
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)

    async def run():
        async with websockets.serve(_handler, config.WEBSOCKET_HOST, config.WEBSOCKET_PORT):
            _ready.set()
            await asyncio.Future()

    _loop.run_until_complete(run())


def start_in_background():
    thread = threading.Thread(target=_serve, name="streamguard-websocket", daemon=True)
    thread.start()
    if not _ready.wait(timeout=5):
        raise RuntimeError("WebSocket server failed to start within 5 seconds")
    return thread
