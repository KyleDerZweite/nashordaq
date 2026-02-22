import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TrackedPlayer

logger = logging.getLogger(__name__)


async def sync_tracked_players(session: AsyncSession) -> None:
    players_path = Path(settings.players_file)
    if not players_path.is_absolute():
        players_path = Path(__file__).resolve().parent.parent / players_path

    if not players_path.exists():
        logger.warning("Players file not found: %s", players_path)
        return

    with open(players_path) as f:
        players_data: list[dict[str, str]] = json.load(f)

    for entry in players_data:
        game_name = entry["game_name"]
        tag_line = entry["tag_line"]
        display_name = entry.get("display_name", game_name)

        result = await session.execute(
            select(TrackedPlayer).where(
                TrackedPlayer.game_name == game_name,
                TrackedPlayer.tag_line == tag_line,
            )
        )
        player = result.scalar_one_or_none()

        if player is None:
            player = TrackedPlayer(
                game_name=game_name,
                tag_line=tag_line,
                display_name=display_name,
            )
            session.add(player)
            logger.info("Added tracked player: %s#%s", game_name, tag_line)
        else:
            player.display_name = display_name

    await session.commit()
