# Nashordaq v0.2.0 — Patch Notes

**Release Date:** 2026-03-20
**Database Reset:** Full economy reset included. All balances restored to 1000 + retroactive playing income. All trading history (orders, holdings, transactions) cleared. Price history replayed from match data.

---

## New Features

### Per-Match Pricing Engine
The market update system no longer treats LP changes as a single aggregate blob. Every ranked match is now individually detected, attributed its LP delta, and priced sequentially. This means a 3-game session where you win two and lose one produces three distinct price movements instead of one averaged move — making the chart dramatically more responsive and interesting.

### Gamba — Leveraged Positions
Place leveraged bets on a randomly selected player. Lock in a cash amount, hold for 24-168 hours, and settle at a multiplier (2.0x-4.0x based on hold duration). Multiple active positions allowed. Can be toggled on/off via system config.

### Poro Flyby Rewards
Random poro flybys appear on your screen. Click them for bonus credits. Six tiers of rewards from common (8 credits) to legendary (89 credits). Spawn rates, paths, and timing are all randomized. Pure engagement candy.

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

### Admin Dashboard & Player Insights
Admins get a dedicated dashboard with detailed per-player statistics, recent activity, and the ability to restore rescue loan access. Order management removed in favor of the automated pipeline.

### Simulation Tool
Test pricing formula changes before deploying them. Edit parameters, replay match history, and visualize how prices would differ — without touching production data.

---

## Economy & Pricing Changes

### Win Streak LP Ratio Dampening
Gains are now dampened by the ratio of average LP lost per loss vs. average LP gained per win (`loss/gain`, clamped 0.3-1.0). Players with inflated LP gains relative to their losses see smaller price increases. This prevents runaway prices from high-LP-gain accounts.

### Negative Streak Amplification
Loss streaks now use a separate, milder beta coefficient (0.06 vs 0.10 for wins). Losing streaks still hurt, but less explosively than win streaks help.

### Low-Price Loss Dampening
Players priced below 15.0 have their losses scaled by `price / 15.0`. A player at 7.50 only takes half the normal loss impact. Prevents penny stocks from cratering to the floor and becoming unrecoverable.

### LP Efficiency Taper
Large LP swings (promotions, demotions) now taper. First 20 LP of gains and 24 LP of losses apply at full strength. Excess LP applies at 25% (gains) or 50% (losses) efficiency.

### Inactivity Decay
Players who haven't had an LP change in 48+ hours see their price drift toward fair value (IPO price at current stats) at 0.075%/hour. Inactive stocks slowly return to fundamentals instead of staying frozen at stale prices.

### Playing Income Rebalance
Switched from minimum-amount model to base payouts. Wins: 0.50 base + variable. Losses: 0.25 base + variable at 0.5x multiplier. Daily diminishing returns after 3 games (65% rate).

### Gamba Settlement Multiplier
Increased to 2.5x base, scaling with hold duration. Higher risk, higher reward.

---

## Infrastructure

### Auth: Username to Email Migration
User identity now anchors on email (from the `Remote-Email` proxy header) instead of the `Remote-User` username. Existing accounts auto-backfill their email on first login. This makes identity stable across proxy/IdP changes.

### Dynamic Rate-Limited Polling
The market update scheduler now calculates its polling interval dynamically based on the Riot API rate limit budget (100 req/2min) and tracked player count. No more hardcoded intervals — scales automatically as players are added or removed.

### Bind-Mount Storage
Database storage switched from a named Podman volume to a bind-mounted `./data/` directory. Simplifies backups (`cp` instead of `podman cp`) and makes the database directly accessible for scripts.

### Recalculation Script
New `scripts/recalculate_all_prices.py` for replaying all prices from scratch after formula changes. Fetches full match history from Riot API, merges with observed data, replays through current pricing formulas, and computes playing income — all in one pass.

### Chart Ranges
Added 1D and 7D chart range options for price history visualization.

---

## Database Reset Details

This release includes a full economy reset due to the pricing formula overhaul:

- **Balances:** Reset to 1000 + retroactive playing income from all tracked matches
- **Prices:** Replayed from match history through the new pricing formulas
- **Match History:** 230 matches across 11 active players (48 observed + 182 backfilled from Riot API)
- **Price History:** 242 data points (1 IPO seed + 1 per match per player)
- **Playing Income:** 230 entries computed inline during replay
- **Cleared:** All orders, holdings, transactions, gamba positions, poro state, bank ledger entries
- **Rescue Loans:** Reset to 1 use remaining per user
