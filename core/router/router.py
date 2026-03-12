from fastapi import APIRouter, WebSocket
from core.controller import controller

app_router = APIRouter(prefix="/api/v1", tags=["Blog"])


# @app_router.post("/blog", status_code=status.HTTP_200_OK, response_model=ResponseModel)
# def invoke_router(requests: Request, body:RequestBody):
#     return controller.response_controller(topic=body.topic)



@app_router.websocket("/ws/{thread_id}")
async def invoke_router(ws : WebSocket, thread_id : str):
    await ws.accept()
    await controller.handle_agent_websocket(websocket=ws,thread_id=thread_id)


    
