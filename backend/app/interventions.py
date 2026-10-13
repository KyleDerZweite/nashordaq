"""Game interventions share the caller's transaction with their activity record."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GameIntervention, User


async def restore_rescue_access(
    session: AsyncSession, actor: User, affected: User
) -> None:
    changed = await session.execute(
        update(User)
        .where(User.id == affected.id, User.rescue_loan_uses_remaining == 0)
        .values(rescue_loan_uses_remaining=1)
        .returning(User.id)
    )
    if changed.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=409, detail="Rescue access is already available"
        )
    session.add(
        GameIntervention(
            actor_user_id=actor.id,
            affected_user_id=affected.id,
            kind="rescue_access_restored",
            previous_uses=0,
            new_uses=1,
            created_at=datetime.now(UTC),
        )
    )
    await session.flush()
