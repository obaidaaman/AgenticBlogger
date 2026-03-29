from fastapi import APIRouter, WebSocket, Request, status, Depends
from core.controller import controller
from core.models.models import SignUpModel, LoginModel
from core.controller import auth_controller


app_router = APIRouter(prefix="/api/v1", tags=["Blog"])


# @app_router.post("/blog", status_code=status.HTTP_200_OK, response_model=ResponseModel)
# def invoke_router(requests: Request, body:RequestBody):
#     return controller.response_controller(topic=body.topic)



@app_router.websocket("/ws/{thread_id}")
async def invoke_router(ws : WebSocket, thread_id : str, current_user = Depends(auth_controller.is_authenticated)):
    await ws.accept()
    await controller.handle_agent_websocket(websocket=ws,thread_id=thread_id)


@app_router.post("/login",status_code=status.HTTP_200_OK)
async def loginUser(request: Request, body: LoginModel):
    return await auth_controller.login(request,body)
    
    
@app_router.post("/signup",status_code=status.HTTP_201_CREATED)
async def signupUser(request: Request, body: SignUpModel ):

    return await auth_controller.signup(request,body)

@app_router.post("/is_auth",status_code=status.HTTP_200_OK)
async def is_authenticated(request : Request):
    return auth_controller.is_authenticated(request)