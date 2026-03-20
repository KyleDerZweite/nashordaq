"""Export anonymized player data from production DB for demo mode seeding.

Usage: cd backend && uv run python scripts/export_demo_seed.py
"""

import json
import sqlite3
import sys
from pathlib import Path

# Champion names used to anonymize player identities
CHAMPION_NAMES = [
    "Aatrox",
    "Ahri",
    "Akali",
    "Akshan",
    "Alistar",
    "Amumu",
    "Anivia",
    "Annie",
    "Aphelios",
    "Ashe",
    "Azir",
    "Bard",
    "Blitzcrank",
    "Brand",
    "Braum",
    "Caitlyn",
    "Camille",
    "Darius",
    "Diana",
    "Draven",
    "Ekko",
    "Elise",
    "Ezreal",
    "Fiora",
    "Fizz",
    "Galio",
    "Gangplank",
    "Garen",
    "Gnar",
    "Gragas",
    "Graves",
    "Gwen",
    "Hecarim",
    "Heimerdinger",
    "Illaoi",
    "Irelia",
    "Ivern",
    "Janna",
    "Jarvan",
    "Jax",
    "Jayce",
    "Jhin",
    "Jinx",
    "Kaisa",
    "Karma",
    "Karthus",
    "Kassadin",
    "Katarina",
    "Kayn",
]

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nashordaq.db"
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "demo" / "demo_seed.json"


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    players = conn.execute("SELECT * FROM tracked_players").fetchall()
    price_history = conn.execute(
        "SELECT * FROM price_history ORDER BY player_id, recorded_at"
    ).fetchall()

    seed_players = []
    for i, player in enumerate(players):
        champion = CHAMPION_NAMES[i % len(CHAMPION_NAMES)]
        seed_players.append(
            {
                "id": player["id"],
                "game_name": champion,
                "tag_line": "DEMO",
                "display_name": champion,
                "puuid": None,
                "summoner_id": None,
                "current_price": player["current_price"],
                "lp_abs": player["lp_abs"],
                "previous_lp_abs": player["previous_lp_abs"],
                "streak": player["streak"],
                "ranked_wins_snapshot": player["ranked_wins_snapshot"],
                "ranked_losses_snapshot": player["ranked_losses_snapshot"],
                "avg_lp_gain_on_win": player["avg_lp_gain_on_win"],
                "avg_lp_loss_on_loss": player["avg_lp_loss_on_loss"],
            }
        )

    seed_price_history = []
    for ph in price_history:
        seed_price_history.append(
            {
                "player_id": ph["player_id"],
                "price": ph["price"],
                "lp_abs": ph["lp_abs"],
                "recorded_at": ph["recorded_at"],
            }
        )

    seed = {
        "players": seed_players,
        "price_history": seed_price_history,
    }

    OUTPUT_PATH.write_text(json.dumps(seed, indent=2))
    print(
        f"Exported {len(seed_players)} players and "
        f"{len(seed_price_history)} price history entries to {OUTPUT_PATH}"
    )
    conn.close()


if __name__ == "__main__":
    main()
