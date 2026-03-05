from fastapi import APIRouter, Depends, Request, status
from core.agent import app
from core.controller import controller
from core.models.models import RequestBody
from core.models.response_model import ResponseModel

app_router = APIRouter(prefix="/api/v1", tags=["Blog"])


@app_router.post("/blog", status_code=status.HTTP_200_OK, response_model=ResponseModel)
def invoke_router(requests: Request, body:RequestBody):
    return controller.response_controller(topic=body.topic)
