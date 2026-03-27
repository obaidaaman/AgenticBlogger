from fastapi import APIRouter, WebSocket, Request, status
from core.controller import controller
from core.models.models import SignUpModel, LoginModel
from core.controller import auth_controller


app_router = APIRouter(prefix="/api/v1", tags=["Blog"])


# @app_router.post("/blog", status_code=status.HTTP_200_OK, response_model=ResponseModel)
# def invoke_router(requests: Request, body:RequestBody):
#     return controller.response_controller(topic=body.topic)



@app_router.websocket("/ws/{thread_id}")
async def invoke_router(ws : WebSocket, thread_id : str):
    await ws.accept()
    await controller.handle_agent_websocket(websocket=ws,thread_id=thread_id)


@app_router.post("/login",status_code=status.HTTP_200_OK)
async def loginUser(request: Request, body: LoginModel):
    return auth_controller.login(body)
    
    
@app_router.post("/signup",status_code=status.HTTP_201_CREATED)
async def signupUser(request: Request, body: SignUpModel ):

    return auth_controller.signup(body)

@app_router.post("/is_auth",status_code=status.HTTP_200_OK)
async def is_authenticated(request : Request):
    return auth_controller.is_authenticated(request)