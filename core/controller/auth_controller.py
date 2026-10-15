
import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import jwt
from pwdlib import PasswordHash
from fastapi import Request, Response, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from core.database import get_db
from core.models.db_models import User, RefreshToken
from core.models.models import SignUpModel, LoginModel

# Password hashing instance (Argon2 via pwdlib)
password_hash = PasswordHash.recommended()

SECRET_KEY = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "agenticblogger-super-secret-jwt-key-2026"
)
ALGORITHM = os.getenv("JWT_ALGORITHM") or os.getenv("ALGORITHM") or "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def _hash_token(token: str) -> str:
    """Hash token before storing in database for security."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, username: str, email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "email": email,
        "type": "access",
        "exp": expires,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> Tuple[str, str, datetime]:
    """Returns (raw_token, token_hash, expires_at)."""
    jti = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": "refresh",
        "exp": expires,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    token_hash = _hash_token(token)
    return token, token_hash, expires


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set access and refresh tokens as HttpOnly cookies."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
    )


def clear_auth_cookies(response: Response):
    """Delete authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")



async def signup(body: SignUpModel, response: Response, db: AsyncSession):
    # Check if username or email already exists
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        )

    hashed_pw = get_password_hash(body.password)
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hashed_pw,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Issue tokens
    access_token = create_access_token(str(user.id), user.username, user.email)
    raw_refresh, refresh_hash, expires_at = create_refresh_token(str(user.id))

    # Persist refresh token in PostgreSQL
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(token_record)
    await db.commit()

    # Set cookies
    set_auth_cookies(response, access_token, raw_refresh)

    return {
        "status": 201,
        "message": "User registered successfully",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
        },
    }


async def login(body: LoginModel, response: Response, db: AsyncSession):
    query = await db.execute(select(User).where(User.username == body.username))
    user = query.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Issue tokens
    access_token = create_access_token(str(user.id), user.username, user.email)
    raw_refresh, refresh_hash, expires_at = create_refresh_token(str(user.id))

    # Store refresh token record
    token_record = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(token_record)
    await db.commit()

    # Set cookies
    set_auth_cookies(response, access_token, raw_refresh)

    return {
        "status": 200,
        "message": "Logged in successfully",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
        },
    }


async def refresh(request: Request, response: Response, db: AsyncSession):
    """Rotate refresh token and issue a fresh access token."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        # Fallback to Authorization header if cookie not sent
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_refresh = auth_header.split(" ")[1]

    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        payload = jwt.decode(raw_refresh, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except Exception:
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    token_hash = _hash_token(raw_refresh)
    token_query = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
        )
    )
    token_record = token_query.scalar_one_or_none()

    if not token_record or token_record.expires_at < datetime.now(timezone.utc):
        clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired or revoked")

    
    token_record.revoked = True

    user_query = await db.execute(select(User).where(User.id == token_record.user_id))
    user = user_query.scalar_one_or_none()
    if not user:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="User not found")

    
    new_access = create_access_token(str(user.id), user.username, user.email)
    new_raw_refresh, new_refresh_hash, new_expires = create_refresh_token(str(user.id))

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=new_refresh_hash,
        expires_at=new_expires,
        revoked=False,
    )
    db.add(new_token_record)
    await db.commit()

    set_auth_cookies(response, new_access, new_raw_refresh)

    return {"status": 200, "message": "Tokens refreshed successfully"}


async def logout(request: Request, response: Response, db: AsyncSession):
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = _hash_token(raw_refresh)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )
        await db.commit()

    clear_auth_cookies(response)
    return {"status": 200, "message": "Logged out successfully"}


async def is_authenticated(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Dependency to authenticate requests from cookies or Bearer token."""
    token = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated: token missing")

    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if data.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token expired")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication error: {e}")

    user_id = data.get("sub")
    query = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = query.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    return {
        "status": 200,
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
    }