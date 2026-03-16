# Economy Backlog

Ideas and improvements for the Nashordaq economy system, roughly ordered by priority.

---

## ~~1. Per-Match LP Tracking (Match-Driven Pricing)~~ DONE

Implemented. The scheduler now detects individual ranked matches via Match-V5 (shared pipeline with playing income), attributes LP deltas to each game, and applies streak + price updates per-match in chronological order. A `PlayerMatch` model stores the full audit trail (`lp_before/after`, `streak_before/after`, `price_before/after`, `lp_delta_source`). Single-game polls get `OBSERVED` attribution; multi-game polls use stored LP averages for `ESTIMATED` splits. Price recalculation from stored data is deterministic. See `docs/ECONOMY_MECHANICS.md` section 3 for details.

---

## ~~2. Inactivity Pressure~~ DONE

Implemented. When a tracked player has no LP change for 48+ hours, the price decays toward the IPO price (based on current LP and win rate) at `0.075%` per hour (time-based, consistent regardless of cycle frequency). Prices above fair value drift down; prices below drift up. Normal pricing resumes the moment LP changes. See `docs/ECONOMY_MECHANICS.md` section 3 (Inactivity Pressure) for details.

---

## ~~3. Minimum Holding Period (Replace Sell Multiplier)~~ DONE

Implemented. After buying shares, those shares cannot be sold for 4 hours (configurable via `min_hold_period_hours`). The lock is per-lot (FIFO). Sells execute at the current market price with no fee or bonus. The old sell multiplier (`calculate_sell_multiplier`, short-hold fee, long-hold bonus) has been removed. Buy-revert grace period is 120 seconds. See `docs/ECONOMY_MECHANICS.md` section 4 for details.

---

## 4. Limited Share Supply + Player-to-Player Trading

**Problem:** Shares are unlimited. Price is 100% LP-driven. Users cannot influence price through trading. There's no scarcity, no reason to time trades, no FOMO or sentiment-driven dynamics.

**Proposed approach: cap the total share supply per stock and enable player-to-player sell orders.**

Instead of an artificial demand premium, introduce real scarcity. When all available shares of a player are bought, nobody can buy more until someone sells. Users who want to sell post limit orders at their desired price, and buyers pick from available offers.

### Share Supply Cap

Each tracked player has a fixed total supply of shares (e.g., 100). The LP-driven price becomes a reference/fair-value indicator, but actual trade prices are set by user offers when P2P trading is used.

Open questions:
- **Fixed vs dynamic supply?** A flat cap (e.g., 100 shares per player) is simplest. A dynamic cap tied to LP or tier adds complexity but could make higher-ranked players more liquid.
- **What happens to existing holdings?** Need a migration strategy if current holdings exceed the new cap.

### Player-to-Player Trading

Users can post sell orders at a price they choose. Other users can buy from those offers. This creates a bid/ask spread and organic price discovery.

- Sell offers sit in an order book until filled or cancelled.
- The LP-driven "market price" is still displayed as a reference.
- Direct market buys (at LP price) could still be allowed when shares are available from the "house" pool, or all buys could go through the order book.

### Position Limits

To prevent one user cornering a stock:
- Max shares per user per stock (e.g., 30% of total supply).
- Or max portfolio concentration (e.g., no more than 50% of net worth in one stock).

### Open Design Questions

This is a major architectural change that needs its own design doc:
- How do "house" shares (not owned by any user) enter circulation? IPO-style release? Always available at LP price?
- Does the LP-driven price still matter for settlement (Gamba, playing income), or does everything move to the order book price?
- How does the UI present the order book without overwhelming a casual audience?
- Impact on Bank failsafe net-worth calculations.

**Complexity:** High. Touches orders, holdings, pricing display, UI, and possibly Gamba settlement. Needs dedicated design before implementation.

---

## ~~5. Negative Streak Amplification~~ DONE

Implemented. Negative streaks now amplify loss-side price movement using a separate beta (`pricing_beta_negative = 0.06`, max 1.6x at streak -10) that is milder than the positive-streak beta (`BETA = 0.10`, max 2.0x at streak 10). This creates visible crash patterns during loss streaks. See `docs/ECONOMY_MECHANICS.md` section 3 for details.

---

## ~~5b. Low-Price Loss Dampening~~ DONE

Implemented. When a stock's price is below `pricing_low_price_threshold` (default `15.0 P`), negative price moves are scaled by `price / threshold`. This caps the percentage loss at the threshold-level rate, preventing low-priced stocks from spiraling into the 1.0 P floor. Gains are unaffected so recovery remains full-speed. See `docs/ECONOMY_MECHANICS.md` section 3 for details.

---

## ~~6. Gamba: Scale Multiplier with Hold Duration~~ DONE

Implemented. Settlement multiplier scales linearly with the random hold duration: 2.0x at 24h to 4.0x at 168h. Both player and duration remain fully random. See `docs/ECONOMY_MECHANICS.md` section 7 for details.

---

## 7. Auth Identity: Switch from Username to Email

**Problem:** `auth.py:70` does `WHERE username == <Remote-User header>`. If someone renames their username in Pangolin, a new user row gets created and their portfolio/balance is lost. The Remote-User header is mutable and not a stable identity key.

**Current users in the DB** (mapped by Remote-User header, examples):
`admin@kylehub.dev`, `kyle`, `redpandaprincess`, `test@kylehub.dev`

**Pangolin injects these headers** (standard behavior):
- `Remote-User` — username (mutable)
- `Remote-Email` — email address (stable, doesn't change)
- `Remote-Name` — display name

**Proposed fix: use Remote-Email as the stable identity key, keep Remote-User as the display name.**

### Required Changes

1. **Add `email` column to `users` table** (unique, indexed) — new lookup key.
2. **Keep `username` column** for display purposes only.
3. **Update `auth.py`** to look up by email, update username on login if it changed.
4. **Add `remote_email_header` config** (default `Remote-Email`).
5. **DB migration for existing rows** — need to fill in emails for the 14 existing users.

### Display Name Strategy

The display name shown in the application should come from what the user sets directly (e.g., their linked League profile name), not from the Zitadel/Pangolin username. On login, upsert the display name in the application with the `Remote-Name` header value as a fallback, but let the user override it via their linked League profile.

### Implementation Sketch

```python
# auth.py — revised lookup
email = request.headers.get(settings.remote_email_header)  # "Remote-Email"
username = request.headers.get(settings.remote_user_header)  # "Remote-User"

user = await session.execute(select(User).where(User.email == email))
user = user.scalar_one_or_none()

if user is None:
    # First login — create user with email as stable key
    user = User(email=email, username=username)
    session.add(user)
elif user.username != username:
    # Username changed in Pangolin — update display name
    user.username = username
```

**Complexity:** Low-medium. The code change is small, but the migration for existing users requires manually mapping the 14 current usernames to their email addresses.
