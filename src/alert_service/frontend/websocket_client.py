# websocket_client.py
import asyncio
import json
import websockets

# Global variable to hold the update callback.
_update_callback = None
ws_connection = None

def set_update_callback(callback):
    """
    Registers a callback function that will be called with the delta payload
    when an "alertUpdated" event is received from the WebSocket server.
    """
    global _update_callback
    _update_callback = callback

async def websocket_client():
    global ws_connection
    uri = "ws://172.184.170.40:8080"  # Replace with your VM's public IP/port.
    async with websockets.connect(uri) as websocket:
        ws_connection = websocket
        print("Connected to WS server.")
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                if data.get("type") == "alertUpdated":
                    process_delta(data["payload"])
            except Exception as e:
                print("Error in websocket client:", e)
                await asyncio.sleep(2)  # minimal backoff before retrying

def process_delta(payload):
    """
    Calls the registered update callback with the payload.
    If no callback is set, the delta is ignored.
    """
    if _update_callback is not None:
        _update_callback(payload)
    else:
        print("No update callback registered; ignoring payload:", payload)

async def start_ws_client():
    while True:
        try:
            await websocket_client()
        except Exception as e:
            print("WebSocket client connection error:", e)
            await asyncio.sleep(5)  # retry after delay

def run_ws_client_in_background():
    """
    Schedules the WebSocket client to run in Panel's asyncio event loop.
    """
    loop = asyncio.get_event_loop()
    loop.create_task(start_ws_client())

async def websocket_shutdown():
    """
    Closes the current WebSocket connection gracefully.
    """
    global ws_connection
    if ws_connection and not ws_connection.closed:
        try:
            await ws_connection.close(code=1000, reason="Dashboard shutdown")
            print("WebSocket connection closed gracefully.")
        except Exception as e:
            print("Error during graceful shutdown:", e)
