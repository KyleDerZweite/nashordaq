# Nashordaq v0.2.0 — Patch Notes

**Release Date:** 2026-03-20
**Database Reset:** Full economy reset included. All balances restored to 1000 + retroactive playing income. All trading history (orders, holdings, transactions) cleared. Price history replayed from match data.

## Features

### Per-Match Pricing Engine
The market update system no longer treats LP changes as a single aggregate blob. Every ranked match is now individually detected, attributed its LP delta, and priced sequentially. This means a 3-game session where you win two and lose one produces three distinct price movements instead of one averaged move — making the chart dramatically more responsive and interesting.

### Gamba — Leveraged Positions
Place leveraged bets on a randomly selected player. Lock in a cash amount, hold for 24-168 hours, and settle at a multiplier (2.0x-4.0x based on hold duration). Multiple active positions allowed. Can be toggled on/off via system config.

### Playing Income
Linked players earn passive credits when their Riot account completes ranked matches. Formula: `BasePayout + (Price * Rate * OutcomeMultiplier * DailyMultiplier)`. Wins pay more than losses. First 3 games per day pay full rate, subsequent games pay at 65%.

### Bank & Rescue Loans
When your debt-adjusted net worth drops below 250, you can claim a one-time 750-credit rescue loan. 2% flat interest charged every 120 hours, with an opening charge on claim. One use per season.

### Market Impact (Slippage)
Orders now move the market price. Buying pushes the price up, selling pushes it down. Impact scales with order size relative to a configurable liquidity depth. Small orders barely move the needle; large orders pay a meaningful premium.

### Minimum Holding Period
Shares must be held for a configurable duration before they can be sold. Prevents instant flip arbitrage during volatile price swings.

### Streamer Mode
Toggle name obfuscation across the entire UI. Hides real player and user names behind generated aliases for streaming or screenshots.

## Database Reset Details

This release includes a full economy reset due to the pricing formula overhaul:

- **Balances:** Reset to 1000 + retroactive playing income from all tracked matches
- **Prices:** Replayed from match history through the new pricing formulas
- **Match History:** 230 matches across 11 active players (48 observed + 182 backfilled from Riot API)
- **Price History:** 242 data points (1 IPO seed + 1 per match per player)
- **Playing Income:** 230 entries computed inline during replay
- **Cleared:** All orders, holdings, transactions, gamba positions, poro state, bank ledger entries
- **Rescue Loans:** Reset to 1 use remaining per user
