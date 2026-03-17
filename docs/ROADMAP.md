# Roadmap

Feature history and open items for the Nashordaq economy system.

## Completed

### 1. Per-Match LP Tracking (Match-Driven Pricing)

The scheduler detects individual ranked matches via Match-V5, attributes LP deltas to each game, and applies streak + price updates per-match in chronological order. A `PlayerMatch` model stores the full audit trail. Single-game polls get `OBSERVED` attribution; multi-game polls use stored LP averages for `ESTIMATED` splits. See `ECONOMY_MECHANICS.md` section 3.

### 2. Inactivity Pressure

When a tracked player has no LP change for 48+ hours, the price decays toward the IPO price at `0.075%` per hour (time-based, consistent regardless of cycle frequency). Prices above fair value drift down; prices below drift up. Normal pricing resumes the moment LP changes. See `ECONOMY_MECHANICS.md` section 3.

### 3. Minimum Holding Period

Shares cannot be sold for 4 hours after purchase (configurable via `min_hold_period_hours`). The lock is per-lot (FIFO). Sells execute at the current market price with no fee or bonus. Buy-revert grace period is 120 seconds. See `ECONOMY_MECHANICS.md` section 4.

### 4a. Market Impact (Trade-Driven Pricing)

Every manual trade moves the market price: buying pushes price up, selling pushes it down. Impact scales linearly with order size (`impact_pct = quantity / liquidity_depth`, default depth `1000`). Gamba orders are exempt. Round-trips always lose money to slippage. See `ECONOMY_MECHANICS.md` section 4.

### 5. Negative Streak Amplification

Negative streaks amplify loss-side price movement using a separate beta (`pricing_beta_negative = 0.06`, max 1.6x at streak -10), milder than the positive-streak beta (`BETA = 0.10`, max 2.0x at streak 10). See `ECONOMY_MECHANICS.md` section 3.

### 5b. Low-Price Loss Dampening

When a stock's price is below `pricing_low_price_threshold` (default `15.0 P`), negative price moves are scaled by `price / threshold`. Gains are unaffected so recovery remains full-speed. See `ECONOMY_MECHANICS.md` section 3.

### 6. Gamba: Scale Multiplier with Hold Duration

Settlement multiplier scales linearly with the random hold duration: 2.0x at 24h to 4.0x at 168h. Both player and duration remain fully random. See `ECONOMY_MECHANICS.md` section 7.

### 7. Auth Identity: Switch from Username to Email

User identity is now based on `Remote-Email` (stable) instead of `Remote-User` (mutable). The `User` model has `email` (identity key) and `display_name` (from Zitadel's `Remote-Name`, updated on each login). Admin role matching uses email. Onboarding only asks for game name and tag line; `TrackedPlayer.display_name` is auto-set from the game name.

## Open (v1)

### 4b. Limited Share Supply + Player-to-Player Trading

Market impact (4a) is live as the first step. Supply cap and P2P trading remain as potential future additions if the group wants more scarcity/FOMO.

**Open questions:**

- Fixed vs dynamic supply cap, and migration for existing holdings
- P2P order book vs house market maker
- Position limits to prevent cornering
- UI for order book without overwhelming casual users

**Complexity:** High. Only pursue if the group outgrows market impact alone.

---

## Future (v2)

The items below require significant architectural changes and are not on the v1 roadmap. They are documented here for future reference.

### Multi-Room Public Access

Make Nashordaq usable by multiple friend groups without requiring everyone to be behind the Pangolin IAP. The app becomes a public website with isolated "rooms" that each function as an independent market.

**Two-tier user model:**

- **IAP users** (Pangolin-authenticated) can create and join rooms.
- **Guests** visit the public site, join a room via code (e.g. `NASH-7K2F`), and create a profile on join. Cannot create rooms.

**Room model:**

- Each room is an independent market with its own tracked players, orders, holdings, and leaderboard.
- Room creator is the admin.
- Player mode per room: *self-link* (members link their own LoL account) or *admin-curated* (admin adds tracked profiles, members just trade).

**Guest identity persistence (unsolved):**

- *Device token* — random bearer token in `localStorage`, admin recovery link if lost. Simplest, no auth stack.
- *Username + passphrase* — works cross-device but requires password hashing.
- *Recovery code* — shown once on profile creation, no user-chosen passwords but easy to lose.
- External auth providers (Matrix, OAuth/OIDC) can be layered on later.

**Data model impact:**

- New `rooms` and `room_members` tables.
- Existing tables (`tracked_players`, `holdings`, `orders`, `price_history`, etc.) gain a `room_id` scope.
- `users` table unifies IAP and guest users; both can be members of multiple rooms.

**Scheduler impact:**

- LP fetching stays global, but price updates and order execution become per-room.
- If two rooms track the same player (same puuid), LP is fetched once but prices computed independently (streak/gamma are per-room state).

**Open questions:**

- Public room listing vs invite-link only
- Room member limits
- Multi-room guest membership
- Room admin disappearance (ownership transfer, auto-expire)
- Riot API rate limits at scale with many rooms and players

