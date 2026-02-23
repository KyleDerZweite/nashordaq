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


async def _get_current_user(request: Request, session: SessionDep) -> User:
    if not _is_trusted_proxy_request(request):
        raise HTTPException(status_code=403, detail="Untrusted proxy source")

    username = request.headers.get(settings.auth_header)
    if not username:
        raise HTTPException(status_code=401, detail="Missing authentication header")

    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(username=username, balance=settings.starting_balance)
        session.add(user)
        try:
            await session.commit()
            await session.refresh(user)
        except IntegrityError:
            await session.rollback()
            result = await session.execute(
                select(User).where(User.username == username)
            )
            user = result.scalar_one()

    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]


def _require_onboarded_user(user: CurrentUser) -> User:
    if user.linked_player_id is None:
        raise HTTPException(status_code=403, detail="Complete onboarding first")
    return user


CurrentOnboardedUser = Annotated[User, Depends(_require_onboarded_user)]
