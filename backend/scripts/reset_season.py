#!/usr/bin/env python3
"""Hard season reset: wipe all transactional data and reset prices to IPO.

Intended for use between seasons to start completely fresh. Preserves user
accounts (id, username, email, display_name, linked_player) and tracked
player identities (id, game_name, tag_line, puuid, summoner_id, current LP)
but clears everything else: orders, transactions, holdings, match records,
price history, debt, poro state, and wealth snapshots.

Player prices are recalculated from their current LP using the IPO formula
with a neutral win rate (0.5). User balances are reset to the starting
balance (1000). Each user gets a fresh ONBOARDING wealth snapshot and each
player gets a single price_history seed row.

No network access required -- uses synchronous sqlite3 only.

Usage (from backend/ directory):
    python scripts/reset_season.py \
        --db-path ../data/nashordaq.db
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

STARTING_BALANCE = 1000.0
PRICE_FLOOR = 1.0

TABLES_TO_CLEAR = [
    "user_poro_states",
    "poro_spawns",
    "playing_income_entries",
    "user_wealth_snapshots",
    "bank_ledger_entries",
    "gamba_positions",
    "holding_lots",
    "transactions",
    "orders",
    "holdings",
    "player_matches",
    "price_history",
]


def _calculate_ipo_price(lp_abs: int) -> float:
    """Inline IPO price with neutral win_rate (0.5).

    Equivalent to app.pricing.calculate_ipo_price(lp_abs, 0.5).
    With win_rate=0.5, the premium term is zero.
    """
    base_price = (lp_abs / 100) + 10
    return max(base_price, PRICE_FLOOR)


def _backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"nashordaq-{timestamp}.db"
    shutil.copy2(db_path, dest)
    print(f"Backup saved to {dest}")
    return dest


def _run(db_path: Path, backup_dir: Path) -> None:
    _backup(db_path, backup_dir)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    now = datetime.now(UTC).isoformat()

    # Reset users
    conn.execute(
        """
        UPDATE users SET
            balance = ?,
            debt_principal = 0.0,
            debt_accrued_interest = 0.0,
            debt_last_accrued_at = NULL,
            debt_next_accrual_at = NULL,
            rescue_loan_uses_remaining = 1
        """,
        (STARTING_BALANCE,),
    )
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"Reset {user_count} user(s) to balance {STARTING_BALANCE}")

    # Read tracked players and compute new IPO prices
    players = conn.execute(
        "SELECT id, game_name, tag_line, lp_abs, current_price FROM tracked_players"
    ).fetchall()

    for player_id, game_name, tag_line, lp_abs, old_price in players:
        new_price = _calculate_ipo_price(lp_abs)
        conn.execute(
            """
            UPDATE tracked_players SET
                current_price = ?,
                previous_lp_abs = lp_abs,
                streak = 0,
                ranked_wins_snapshot = NULL,
                ranked_losses_snapshot = NULL,
                avg_lp_gain_on_win = NULL,
                avg_lp_loss_on_loss = NULL,
                last_updated = NULL,
                last_match_pricing_at = NULL,
                last_playing_income_match_id = NULL,
                last_playing_income_match_end_at = NULL
            WHERE id = ?
            """,
            (new_price, player_id),
        )
        print(
            f"  {game_name}#{tag_line}: "
            f"LP={lp_abs}, {old_price:.2f} -> {new_price:.2f} (IPO)"
        )

    # Clear all transactional tables
    for table in TABLES_TO_CLEAR:
        deleted = conn.execute(f"DELETE FROM {table}").rowcount  # noqa: S608
        if deleted:
            print(f"  Cleared {table}: {deleted} row(s)")

    # Seed initial price history
    for player_id, _, _, lp_abs, _ in players:
        new_price = _calculate_ipo_price(lp_abs)
        conn.execute(
            """
            INSERT INTO price_history (player_id, price, lp_abs, recorded_at)
            VALUES (?, ?, ?, ?)
            """,
            (player_id, new_price, lp_abs, now),
        )

    # Seed initial wealth snapshots
    user_ids = [row[0] for row in conn.execute("SELECT id FROM users").fetchall()]
    for user_id in user_ids:
        conn.execute(
            """
            INSERT INTO user_wealth_snapshots
                (user_id, source, cash_balance, holdings_value,
                 active_gamba_value, debt_outstanding, net_worth, recorded_at)
            VALUES (?, 'ONBOARDING', ?, 0.0, 0.0, 0.0, ?, ?)
            """,
            (user_id, STARTING_BALANCE, STARTING_BALANCE, now),
        )

    conn.commit()
    conn.close()

    print(
        f"\nSeason reset complete: {user_count} user(s), "
        f"{len(players)} player(s) re-priced to IPO."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hard season reset: wipe history, reset to IPO prices."
    )
    parser.add_argument("--db-path", type=Path, required=True, help="Path to SQLite DB")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("./backups"),
        help="Directory for backup (default: ./backups)",
    )
    args = parser.parse_args()

    if not args.db_path.exists():
        parser.error(f"DB file not found: {args.db_path}")

    _run(args.db_path, args.backup_dir)


if __name__ == "__main__":
    main()
