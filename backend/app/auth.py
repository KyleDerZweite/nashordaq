import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import get_session
from app.models import AccessToken, AuthSession, User

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SESSION_COOKIE = "nashordaq_session"
SESSION_LIFETIME = timedelta(days=7)
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def utc_now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# Bound memory used by concurrent password checks in the single application process.
_password_work_limit = BoundedSemaphore(2)


def _password_verifier(password: str, salt: str, n: int, r: int, p: int) -> bytes:
    with _password_work_limit:
        return hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=n,
            r=r,
            p=p,
            maxmem=256 * 1024 * 1024,
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    verifier = _password_verifier(password, salt, 2**17, 8, 1)
    return f"scrypt$131072$8$1${salt}${verifier.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt, verifier = encoded.split("$")
        if algorithm != "scrypt":
            return False
        actual = _password_verifier(password, salt, int(n), int(r), int(p))
        return hmac.compare_digest(actual.hex(), verifier)
    except (ValueError, TypeError):
        return False


DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


async def setup_is_open(session: AsyncSession) -> bool:
    if settings.demo_mode_enabled:
        return False
    administrator = await session.scalar(select(User.id).where(User.is_admin))
    completed = await session.scalar(
        select(AccessToken.id)
        .where(AccessToken.kind == "setup", AccessToken.consumed_at.is_not(None))
        .limit(1)
    )
    return administrator is None and completed is None


async def initialize_setup(session: AsyncSession) -> None:
    if not await setup_is_open(session):
        return
    await session.execute(delete(AccessToken).where(AccessToken.kind == "setup"))
    token = secrets.token_urlsafe(32)
    session.add(AccessToken(token_hash=hash_token(token), kind="setup"))
    await session.commit()
    logger.warning(
        "Initial administrator setup: %s/setup?token=%s",
        settings.public_url.rstrip("/"),
        token,
    )


def get_user_role(user: User) -> str:
    return "admin" if user.is_admin and not user.is_demo else "player"


def is_admin_user(user: User) -> bool:
    return get_user_role(user) == "admin"


def is_demo_user(user: User) -> bool:
    return user.is_demo


async def lookup_session_user(session: AsyncSession, token: str | None) -> User | None:
    if settings.demo_mode_enabled:
        return None
    if not token:
        return None
    return await session.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.expires_at > utc_now(),
        )
    )


async def get_current_user(request: Request, session: SessionDep) -> User:
    user = await lookup_session_user(session, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Login required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _require_onboarded_user(user: CurrentUser) -> User:
    if is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin users cannot trade")
    if not user.is_demo and user.linked_player_id is None:
        raise HTTPException(status_code=403, detail="Complete onboarding first")
    return user


CurrentOnboardedUser = Annotated[User, Depends(_require_onboarded_user)]


def _require_admin_user(user: CurrentUser) -> User:
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentAdminUser = Annotated[User, Depends(_require_admin_user)]


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter a username without control characters")
        return value


class SetupCredentials(Credentials):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=12, max_length=1024)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=settings.public_url.startswith("https://"),
        samesite="strict",
        path="/",
    )


async def create_session(session: AsyncSession, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=utc_now() + SESSION_LIFETIME,
        )
    )
    await session.commit()
    _set_session_cookie(response, token)


@router.get("/status")
async def auth_status(session: SessionDep) -> dict[str, bool]:
    return {
        "setup_required": await setup_is_open(session),
        "demo_mode_enabled": settings.demo_mode_enabled,
    }


@router.post("/setup", status_code=201)
async def setup(
    body: SetupCredentials, session: SessionDep, response: Response
) -> dict[str, str]:
    if settings.demo_mode_enabled:
        raise HTTPException(status_code=403, detail="Setup unavailable in demo mode")
    verifier = await run_in_threadpool(hash_password, body.password)
    consumed = await session.execute(
        update(AccessToken)
        .where(
            AccessToken.token_hash == hash_token(body.token),
            AccessToken.kind == "setup",
            AccessToken.consumed_at.is_(None),
            AccessToken.revoked_at.is_(None),
        )
        .values(consumed_at=utc_now())
        .returning(AccessToken.id)
    )
    if consumed.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=400, detail="Setup link is invalid or already used"
        )
    user = User(
        username=body.username,
        display_name=body.username,
        password_hash=verifier,
        is_admin=True,
        balance=settings.starting_balance,
    )
    session.add(user)
    try:
        await session.flush()
        await create_session(session, user, response)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Setup has already completed"
        ) from None
    return {"status": "ok"}


@router.post("/login")
async def login(
    body: Credentials, session: SessionDep, response: Response
) -> dict[str, str]:
    if settings.demo_mode_enabled:
        raise HTTPException(status_code=403, detail="Demo login is not available yet")
    user = await session.scalar(
        select(User).where(User.username == body.username, User.is_demo.is_(False))
    )
    # Use the same costly verifier for unknown users to avoid a username timing oracle.
    encoded = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    valid = await run_in_threadpool(verify_password, body.password, encoded)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    await create_session(session, user, response)
    return {"status": "ok"}


@router.get("/session")
async def current_session(user: CurrentUser) -> dict[str, bool]:
    return {"authenticated": True}


@router.post("/logout")
async def logout(
    request: Request, response: Response, user: CurrentUser, session: SessionDep
) -> dict[str, str]:
    await session.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == hash_token(request.cookies[SESSION_COOKIE]),
            AuthSession.user_id == user.id,
        )
    )
    await session.commit()
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.public_url.startswith("https://"),
        samesite="strict",
    )
    return {"status": "ok"}
