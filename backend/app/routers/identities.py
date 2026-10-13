"""Identity data for the shared frontend presentation interface."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.database import get_session
from app.identities import AliasPoolExhausted  # register persistence creation invariant
from app.models import IdentityAlias, TrackedPlayer, User

__all__ = ["AliasPoolExhausted", "router"]
router = APIRouter(tags=["identities"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


class UserIdentity(BaseModel):
    user_id: int
    username: str
    linked_player_id: int | None
    game_name: str | None
    tag_line: str | None
    streamer_alias: str


class PlayerIdentity(BaseModel):
    player_id: int
    username: str | None
    game_name: str
    tag_line: str
    streamer_alias: str


class IdentityDirectory(BaseModel):
    users: list[UserIdentity]
    players: list[PlayerIdentity]


@router.get("/identities", response_model=IdentityDirectory)
async def identity_directory(
    requester: CurrentUser, session: SessionDep
) -> IdentityDirectory:
    # Demo visitors see only their own temporary identity, never other visitors'
    # generated usernames or regular accounts. The market is shared.
    members = list(
        await session.scalars(
            select(User).where(
                User.id == requester.id
                if requester.is_demo
                else User.is_demo.is_(False)
            )
        )
    )
    visible_member_ids = {member.id for member in members}
    private_player_ids = set(
        await session.scalars(
            select(User.linked_player_id).where(
                User.id.not_in(visible_member_ids), User.linked_player_id.is_not(None)
            )
        )
    )
    players = list(await session.scalars(select(TrackedPlayer)))
    aliases = list(await session.scalars(select(IdentityAlias)))
    user_aliases = {
        row.user_id: row.alias for row in aliases if row.user_id is not None
    }
    player_aliases = {
        row.player_id: row.alias for row in aliases if row.player_id is not None
    }
    players_by_id = {player.id: player for player in players}
    users_by_player = {
        member.linked_player_id: member
        for member in members
        if member.linked_player_id is not None
    }
    return IdentityDirectory(
        users=[
            UserIdentity(
                user_id=member.id,
                username=member.username,
                linked_player_id=member.linked_player_id,
                game_name=players_by_id[member.linked_player_id].game_name
                if member.linked_player_id in players_by_id
                else None,
                tag_line=players_by_id[member.linked_player_id].tag_line
                if member.linked_player_id in players_by_id
                else None,
                streamer_alias=user_aliases[member.id],
            )
            for member in members
        ],
        players=[
            PlayerIdentity(
                player_id=player.id,
                username=users_by_player[player.id].username
                if player.id in users_by_player
                else None,
                game_name=player_aliases[player.id]
                if player.id in private_player_ids
                else player.game_name,
                tag_line="" if player.id in private_player_ids else player.tag_line,
                streamer_alias=user_aliases[users_by_player[player.id].id]
                if player.id in users_by_player
                else player_aliases[player.id],
            )
            for player in players
        ],
    )
