"""
router.py — FastAPI routes for Authentication and WebSocket Agent interactions.
"""

import os
import jwt
from fastapi import APIRouter, WebSocket, Request, Response, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.controller import controller, auth_controller
from core.models.models import SignUpModel, LoginModel

app_router = APIRouter(prefix="/api/v1", tags=["Blog & Auth"])

@app_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup_user(
    body: SignUpModel,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user and set access + refresh tokens in HttpOnly cookies."""
    return await auth_controller.signup(body=body, response=response, db=db)

@app_router.post("/login", status_code=status.HTTP_200_OK)
async def login_user(
    body: LoginModel,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and set access + refresh tokens in HttpOnly cookies."""
    return await auth_controller.login(body=body, response=response, db=db)


@app_router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_tokens(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token and issue a fresh access token in cookies."""
    return await auth_controller.refresh(request=request, response=response, db=db)


@app_router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Revoke refresh token and clear authentication cookies."""
    return await auth_controller.logout(request=request, response=response, db=db)


@app_router.get("/is_auth", status_code=status.HTTP_200_OK)
@app_router.get("/me", status_code=status.HTTP_200_OK)
async def check_authenticated(current_user: dict = Depends(auth_controller.is_authenticated)):
    """Check authentication status using cookie or Bearer token."""
    return current_user



@app_router.websocket("/ws/{thread_id}")
async def invoke_agent_websocket(ws: WebSocket, thread_id: str):
    """
    WebSocket endpoint for real-time human-in-the-loop blog generation.
    Authenticates via HttpOnly cookie or ?token= query parameter.
    """
    
    token = ws.cookies.get("access_token") or ws.query_params.get("token")
    user_info = None

    if token:
        try:
            secret = (
                os.getenv("JWT_SECRET_KEY")
                or os.getenv("SECRET_KEY")
                or "agenticblogger-super-secret-jwt-key-2026"
            )
            algorithm = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM") or "HS256"
            payload = jwt.decode(token, secret, algorithms=[algorithm])
            if payload.get("type") == "access":
                user_info = payload
        except Exception:
            pass

    await ws.accept()
    await controller.handle_agent_websocket(
        websocket=ws,
        thread_id=thread_id,
        user_info=user_info,
    )