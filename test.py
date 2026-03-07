import asyncio
import json
import websockets
import uuid
async def test():
    thread_id = str(uuid.uuid4())
    uri = f"ws://127.0.0.1:8000/api/v1/ws/{thread_id}"

    async with websockets.connect(uri) as ws:

        await ws.send(json.dumps({
            "topic": "LangGraph architecture"
        }))

        while True:
            msg = await ws.recv()
            print(msg)

            data = json.loads(msg)

            if data["type"] == "interrupt":
                await ws.send(json.dumps({
                    "action": "approve"
                }))

asyncio.run(test())