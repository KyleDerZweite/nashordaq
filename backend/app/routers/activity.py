from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_session
from app.models import GameIntervention, TrackedPlayer, User
from app.schemas import ActivityIdentityResponse, GameInterventionResponse

router = APIRouter(tags=["activity"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/activity", response_model=list[GameInterventionResponse])
async def list_activity(
    user: CurrentUser, session: SessionDep
) -> list[GameInterventionResponse]:
    if user.is_demo:
        return []
    events = (
        await session.scalars(
            select(GameIntervention).order_by(GameIntervention.id.desc())
        )
    ).all()
    user_ids = {event.actor_user_id for event in events} | {
        event.affected_user_id for event in events
    }
    identities: dict[int, ActivityIdentityResponse] = {}
    for member, player in (
        await session.execute(
            select(User, TrackedPlayer)
            .outerjoin(TrackedPlayer, TrackedPlayer.id == User.linked_player_id)
            .where(User.id.in_(user_ids))
        )
    ).all():
        identities[member.id] = ActivityIdentityResponse(
            user_id=member.id,
            username=member.username,
            linked_player_id=member.linked_player_id,
            game_name=player.game_name if player else None,
            tag_line=player.tag_line if player else None,
        )
    return [
        GameInterventionResponse(
            id=event.id,
            actor=identities[event.actor_user_id],
            affected=identities[event.affected_user_id],
            kind=event.kind,
            previous_uses=event.previous_uses,
            new_uses=event.new_uses,
            created_at=event.created_at.replace(tzinfo=UTC),
        )
        for event in events
    ]
