import secrets
from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserRole = str


@lru_cache(maxsize=1)
def _trusted_proxy_networks(cidr_csv: str) -> tuple:
    cidrs = [c.strip() for c in cidr_csv.split(",") if c.strip()]
    return tuple(ip_network(cidr, strict=False) for cidr in cidrs)


def _is_trusted_proxy_request(request: Request) -> bool:
    if not settings.enforce_trusted_proxy:
        return True

    client_host = request.client.host if request.client else None
    if client_host is None:
        return False

    try:
        client_ip = ip_address(client_host)
    except ValueError:
        return False

    return any(
        client_ip in network
        for network in _trusted_proxy_networks(settings.trusted_proxy_cidrs)
    )


def get_user_role(email: str) -> UserRole:
    configured_admin_users = tuple(
        candidate.strip().casefold()
        for candidate in settings.admin_remote_users.split(",")
        if candidate.strip()
    )
    if email.casefold() in configured_admin_users:
        return "admin"
    return "player"


def is_admin_email(email: str) -> bool:
    return get_user_role(email) == "admin"


def is_admin_user(user: User) -> bool:
    return is_admin_email(user.email or user.username)


def is_demo_user(user: User) -> bool:
    return user.is_demo


async def _get_current_user(request: Request, session: SessionDep) -> User:
    email = request.headers.get(settings.remote_email_header)
    username = request.headers.get(settings.auth_header, "")

    # Demo mode: create or resume ephemeral session when no proxy headers
    if settings.demo_mode_enabled and not email and not username:
        cookie_token = request.cookies.get("nashordaq_demo_session")
        if cookie_token:
            result = await session.execute(
                select(User).where(
                    User.username == f"demo_{cookie_token}",
                    User.is_demo == True,  # noqa: E712
                )
            )
            user = result.scalar_one_or_none()
            if user is not None:
                return user

        # Create new demo user
        token = secrets.token_urlsafe(16)
        user = User(
            username=f"demo_{token}",
            email=f"demo_{token}@demo.nashordaq.local",
            display_name="",
            balance=settings.starting_balance,
            is_demo=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        request.state.demo_session_token = token
        return user

    if not _is_trusted_proxy_request(request):
        raise HTTPException(status_code=403, detail="Untrusted proxy source")

    display_name = request.headers.get(settings.remote_name_header, "")

    if not email and not username:
        raise HTTPException(status_code=401, detail="Missing authentication header")

    user: User | None = None
    needs_commit = False

    if email:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    # Fallback: try username lookup for pre-migration users without email
    if user is None and username:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        # Backfill email on first login with the new header
        if user is not None and email and user.email is None:
            user.email = email
            needs_commit = True

    if user is None:
        identity = email or username
        user = User(
            username=username or email,
            email=email,
            display_name=display_name or email or username,
            balance=settings.starting_balance,
        )
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            await session.rollback()
            if email:
                result = await session.execute(select(User).where(User.email == email))
            else:
                result = await session.execute(
                    select(User).where(User.username == identity)
                )
            user = result.scalar_one()

    # Update display name from Zitadel if it changed
    if display_name and user.display_name != display_name:
        user.display_name = display_name
        needs_commit = True

    if needs_commit:
        await session.commit()
        await session.refresh(user)

    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]


def _require_onboarded_user(user: CurrentUser) -> User:
    if user.is_demo:
        return user

    if is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin users cannot trade")

    if user.linked_player_id is None:
        raise HTTPException(status_code=403, detail="Complete onboarding first")
    return user


CurrentOnboardedUser = Annotated[User, Depends(_require_onboarded_user)]


def _require_admin_user(user: CurrentUser) -> User:
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


CurrentAdminUser = Annotated[User, Depends(_require_admin_user)]
