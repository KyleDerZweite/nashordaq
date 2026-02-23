from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_session
from app.models import TrackedPlayer, User
from app.schemas import UserOnboardingCreate, UserResponse

router = APIRouter(tags=["user"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        balance=user.balance,
        linked_player_id=user.linked_player_id,
        onboarding_complete=user.linked_player_id is not None,
        created_at=user.created_at,
    )


@router.get("/user/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    return _to_user_response(user)


@router.post("/user/onboarding", response_model=UserResponse)
async def complete_onboarding(
    body: UserOnboardingCreate,
    user: CurrentUser,
    session: SessionDep,
) -> UserResponse:
    if user.linked_player_id is not None:
        raise HTTPException(status_code=409, detail="Onboarding already completed")

    game_name = body.game_name.strip()
    tag_line = body.tag_line.strip().lstrip("#")
    display_name = body.display_name.strip()

    if not game_name or not tag_line or not display_name:
        raise HTTPException(status_code=400, detail="All fields are required")

    existing_result = await session.execute(
        select(TrackedPlayer).where(
            TrackedPlayer.game_name == game_name,
            TrackedPlayer.tag_line == tag_line,
        )
    )
    existing_player = existing_result.scalar_one_or_none()
    if existing_player is not None:
        raise HTTPException(status_code=409, detail="Player is already tracked")

    player = TrackedPlayer(
        game_name=game_name,
        tag_line=tag_line,
        display_name=display_name,
    )
    session.add(player)
    await session.flush()

    linked_result = await session.execute(
        select(User).where(User.linked_player_id == player.id)
    )
    already_linked = linked_result.scalar_one_or_none()
    if already_linked is not None:
        raise HTTPException(status_code=409, detail="Player is already linked")

    user.linked_player_id = player.id
    await session.commit()
    await session.refresh(user)
    return _to_user_response(user)
