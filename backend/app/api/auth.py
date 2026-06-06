"""Auth API: register / login / me / Google OAuth."""
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DB
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DB) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DB) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        email=user.email,
        name=user.name,
        plan=user.plan,
        token_credits=getattr(user, "token_credits", 0.0) or 0.0,
        token_credits_monthly=getattr(user, "token_credits_monthly", 0.0) or 0.0,
        frozen_credits=getattr(user, "frozen_credits", 0.0) or 0.0,
        is_admin=getattr(user, "is_admin", False),
    )


# ---------- Google OAuth ----------

def _google_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI)


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    if not _google_configured():
        raise HTTPException(status_code=503, detail="Google OAuth не настроен")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(request: Request, db: DB) -> RedirectResponse:
    if not _google_configured():
        raise HTTPException(status_code=503, detail="Google OAuth не настроен")
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Google token exchange failed: {token_resp.text}")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token from Google")
        info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if info_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Google userinfo failed")
        info = info_resp.json()

    google_id = info.get("id")
    email = info.get("email")
    name = info.get("name") or (email.split("@")[0] if email else None)
    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Incomplete Google profile")

    user = await db.scalar(select(User).where(User.google_id == google_id))
    if user is None:
        user = await db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.google_id = google_id
        else:
            user = User(email=email, google_id=google_id, name=name)
            db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    redirect_to = f"{settings.FRONTEND_URL.rstrip('/')}/login?token={token}"
    return RedirectResponse(url=redirect_to)
