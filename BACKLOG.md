# Economy Backlog

Ideas and improvements for the Nashordaq economy system, roughly ordered by priority.

---

## ~~1. Per-Match LP Tracking (Match-Driven Pricing)~~ ✅ DONE

**Problem:** The current scheduler polls league-v4 for an LP snapshot every few minutes and computes an aggregate `delta_lp`. This has multiple downstream issues:

- **Streak accuracy:** If 2 wins happen between polls, streak only increments by 1 instead of 2. Identical player performance produces different prices depending on polling timing.
- **LP averages are approximations:** The EMA only learns from "pure" refreshes (only wins or only losses changed). Mixed refreshes are discarded.
- **Recalculation is guesswork:** The `recalculate_player_price_from_matches.py` script assumes fixed LP per win/loss because actual per-game LP was never stored.
- **No audit trail:** Price movements can't be traced back to specific matches.

**Proposed approach: store every match and attribute LP deltas to individual games.**

The key insight: we already fetch match-v5 history for playing income (`_apply_playing_income_for_player`). We can piggyback on that to also record per-match LP changes.

**Why multi-game polls are rare:** A typical LoL game takes ~30 minutes. With the current polling interval of `ceil(N * 0.5)` minutes per player (1 API call each via league-v4/entries/by-puuid at 20000 req/10s), we'd need 30+ tracked players before the interval exceeds one game length. For a friends group of 5-10, most polls will catch exactly 0 or 1 new games. Multi-game polls only happen when the scheduler is down or during back-to-back remakes/surrenders.

### Data Model

New model `PlayerMatch` to store every detected ranked match:

```python
class PlayerMatch(Base):
    __tablename__ = "player_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    match_id: Mapped[str] = mapped_column(String(64))
    win: Mapped[bool]
    lp_before: Mapped[int] = mapped_column(Integer)
    lp_after: Mapped[int] = mapped_column(Integer)
    lp_delta: Mapped[int] = mapped_column(Integer)
    # Whether lp_delta was directly observed (single-game poll) or estimated
    # (split from multi-game poll).
    lp_delta_source: Mapped[str] = mapped_column(String(16))  # "observed" | "estimated"
    streak_before: Mapped[int] = mapped_column(Integer)
    streak_after: Mapped[int] = mapped_column(Integer)
    price_before: Mapped[float] = mapped_column(Float)
    price_after: Mapped[float] = mapped_column(Float)
    game_duration_seconds: Mapped[int] = mapped_column(Integer)
    completed_at: Mapped[datetime] = mapped_column(index=True)
    recorded_at: Mapped[datetime] = mapped_column(insert_default=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "match_id", name="uq_player_match"),
    )
```

### Revised Scheduler Flow

```
For each tracked player:
  1. league-v4/entries/by-puuid → new LP snapshot        [1 API call, 20000/10s]
  2. match-v5/matches/by-puuid → new match IDs           [already done for playing income]
  3. For each new match: match-v5/matches/{id} → details  [already done for playing income]
  4. Correlate LP delta with detected matches
  5. Apply per-match price updates
```

Steps 2-3 already happen for playing income. The only new work is correlating LP deltas with matches (step 4) and applying price updates per-match instead of per-poll (step 5).

### LP Attribution Logic

**Single-game poll (most common case, ~95% of polls for <10 players):**
```
new_matches = [1 match detected]
lp_delta = new_lp_abs - old_lp_abs
→ Attribute entire lp_delta to the single match.
→ lp_delta_source = "observed"
→ Apply one update_streak + calculate_new_price.
```

**Multi-game poll (rare, same direction):**
```
new_matches = [match_a (win), match_b (win)]  # from match-v5, chronologically ordered
lp_delta = +38 total
→ Split: lp_per_win = 38 / 2 = 19 each (or use stored avg_lp_gain_on_win if available)
→ lp_delta_source = "estimated"
→ Apply update_streak + calculate_new_price TWICE, once per match.
```

**Multi-game poll (rare, mixed direction):**
```
new_matches = [match_a (loss), match_b (win)]  # chronological order from match-v5
lp_delta = +5 total, 1 win + 1 loss
→ Use stored averages: avg_gain=22, avg_loss=17
→ Estimated: loss_lp = -17, win_lp = +22 (sum = +5, matches total delta)
→ If averages unavailable or don't reconcile: fall back to even split or
  attribute proportionally (e.g., loss = -(|delta| * loss_share), win = remainder)
→ Apply updates in chronological order: loss first, then win.
```

**Zero-game poll with LP change (promotion/demotion LP adjustments):**
```
lp_delta != 0 but no new matches detected
→ Record as a system adjustment (no PlayerMatch row).
→ Apply single aggregate price update (current behavior).
```

### Benefits Over Current System

| Aspect | Current | With per-match tracking |
|--------|---------|------------------------|
| Streak accuracy | Per-poll (can miss games) | Per-game (exact) |
| LP averages | EMA on pure refreshes only | Direct per-game observations |
| Price recalculation | Guesswork (assumed fixed LP) | Deterministic replay from stored data |
| Audit trail | PriceHistory only | Full match-to-price-movement chain |
| Playing income correlation | Separate match detection | Shared match detection pipeline |

### Recalculation Script Improvement

With `PlayerMatch` rows stored, the recalculate script becomes trivial:

```python
matches = session.query(PlayerMatch).filter_by(player_id=player.id).order_by(completed_at)
price = calculate_ipo_price(matches[0].lp_before)
streak = 0
for match in matches:
    streak = update_streak(streak, match.lp_delta)
    price = calculate_new_price(price, match.lp_delta, streak, ...)
```

No Riot API calls needed. No LP assumptions. Fully deterministic.

### Implementation Plan

1. Add `PlayerMatch` model and migration.
2. Merge match detection from playing income and pricing into a shared pipeline. Currently `_apply_playing_income_for_player` fetches matches independently. Refactor so the scheduler detects new matches once per player and passes them to both the pricing engine and playing income.
3. Implement LP attribution logic (single-game observed, multi-game estimated).
4. Apply per-match price updates instead of aggregate delta.
5. Update `_learn_player_lp_averages` to use direct per-game LP instead of EMA (or keep EMA as a fallback for estimated splits).
6. Update the recalculate script to replay from `PlayerMatch` rows.

### API Budget Impact

No additional API calls. Match-v5 is already fetched for playing income. League-v4 is already fetched for LP snapshots. We're just correlating data that's already being retrieved.

**Complexity:** Medium-high. The match detection refactor is the biggest piece. LP attribution for multi-game polls needs careful handling. But the payoff is large: accurate per-game pricing, deterministic recalculation, and a complete audit trail.

---

## 2. Inactivity Pressure

**Problem:** When a player stops playing, their price freezes indefinitely. Holdings in inactive players become risk-free stores of value. In a real stock market, uncertainty from low activity causes price drift. This removes a strategic dimension: there's no incentive to sell an inactive player's stock.

**Proposed approach: slow decay toward fair value.**

Define a fair-value baseline as the IPO formula: `(LP_abs / 100) + 10`. When a tracked player has had no LP change for a configurable duration, begin pulling the price toward this baseline by a small percentage per cycle.

```python
# In the scheduler, when delta_lp == 0:
hours_since_update = (now - player.last_updated).total_seconds() / 3600
if hours_since_update > INACTIVITY_THRESHOLD_HOURS:  # e.g., 48h
    fair_value = (player.lp_abs / 100) + 10
    decay_rate = INACTIVITY_DECAY_RATE  # e.g., 0.002 per cycle (~0.2%)
    price_diff = player.current_price - fair_value
    if abs(price_diff) > 0.01:
        player.current_price -= price_diff * decay_rate
        # Record price history so chart shows the drift
```

**Config knobs:**
- `pricing_inactivity_threshold_hours: float = 48.0` -- hours without LP change before decay starts.
- `pricing_inactivity_decay_rate: float = 0.002` -- fraction of (price - fair_value) to decay per cycle.

**Behavior:**
- A player priced at 45 with fair value 35 would slowly drift down: 45 -> 44.98 -> 44.96 -> ... approaching 35 asymptotically.
- A player priced below fair value (e.g., after a loss streak) would slowly recover upward.
- The moment the player plays again and LP changes, normal pricing resumes and the decay stops.
- The decay is per-cycle (every ~1.25 min per player), so even 0.2% adds up over days of inactivity.

**What users see:** A slowly declining (or recovering) chart line during player inactivity. No explanation is given -- it just looks like natural market drift, which adds to the stock market feel.

**Complexity:** Low. A few lines in the `delta_lp == 0` branch of the scheduler.

---

## 3. Sell Multiplier: Increase or Remove

**Problem:** The current hold bonus/penalty is +/-2% max. On a 40 P stock with 10 shares, that's +/-8 P. With 1000 P starting balance, this is noise. It doesn't meaningfully influence sell timing decisions.

**Option A: Increase to make it matter.**

Raise the rates so players actually feel the difference:

```
Short hold fee:     -5% at 0h, ramping to 0% at 6h (from -2%)
Long hold bonus:    +5% after 24h (from +2% after 12h)
```

At 40 P * 10 shares = 400 P total, a 5% fee/bonus = 20 P. That's noticeable on a 1000 P balance.

Could also make the long-hold bonus scale with duration (logarithmic), so diamond-hands holding is rewarded:

```python
# Progressive bonus: grows with hold time, diminishing returns
if held_hours >= long_hold_bonus_start_hours:
    days_held = held_hours / 24
    bonus = base_bonus * math.log2(1 + days_held)  # e.g., 0.02 * log2(1+days)
    return 1 + min(bonus, max_bonus_cap)  # cap at e.g., 10%
```

**Option B: Remove entirely.**

Delete `calculate_sell_multiplier`, the FIFO lot tracking for hold duration, and the `HoldingLot` model complexity. Sells just execute at market price. Reduces code and cognitive load.

**Recommendation:** Option A with moderate numbers (5% fee, 5% base bonus, logarithmic scaling capped at 10%) is probably more fun than removing it. But if simplicity is the priority, Option B is fine since the current 2% is essentially the same as having no multiplier at all.

**Complexity:** Trivial for either option. Config changes + one function edit.

---

## 4. Demand-Driven Price Component

**Problem:** Price is 100% LP-driven. Users can observe but cannot influence price through trading. This is the biggest gap between Nashordaq and a real stock market. There's no reason to time your trades, no FOMO, no bubbles, no crashes driven by sentiment.

**Proposed approach: net-demand premium.**

Track rolling buy/sell volume per player over a window. Compute a small demand premium that nudges the price up when buying pressure is high and down when selling pressure is high.

**Data model addition:**
```python
# On TrackedPlayer:
net_demand_shares_24h: float  # rolling net buy - sell shares in last 24h
```

Updated each time an order executes:
```python
# In order execution:
if side == BUY:
    player.net_demand_shares_24h += quantity
elif side == SELL:
    player.net_demand_shares_24h -= quantity
```

Decayed periodically by the scheduler (exponential decay toward 0):
```python
# Each market cycle:
player.net_demand_shares_24h *= DEMAND_DECAY_RATE  # e.g., 0.995 per cycle
```

**Price integration (two possible approaches):**

*Approach A -- Additive premium on price delta:*
```python
demand_premium = clamp(player.net_demand_shares_24h * DEMAND_SENSITIVITY, -max, +max)
# e.g., DEMAND_SENSITIVITY = 0.05, max = 3% of current price
player.current_price += demand_premium
```

*Approach B -- Multiplicative spread on execution price:*
```python
# Buy price slightly higher when demand is high:
buy_spread  = 1 + clamp(net_demand * 0.001, 0, 0.03)
# Sell price slightly lower when supply pressure is high:
sell_spread = 1 - clamp(-net_demand * 0.001, 0, 0.03)
```

Approach A is simpler and affects the canonical price everyone sees. Approach B only affects execution and keeps the "true" price LP-driven, which might be cleaner.

**What users see:** "Everyone is buying Player X" -> price creeps up slightly beyond what LP alone justifies -> early buyers profit, late buyers pay a premium -> organic bubble/crash dynamics.

**Complexity:** Medium. Needs a new model field, order execution hooks, scheduler decay, and a decision on where the premium is applied. Worth designing carefully before implementing since it touches the core pricing path.

---

## 5. Negative Streak Amplification

**Problem:** Only positive streaks amplify price movement. A player on a 10-loss streak loses the same LP-to-price ratio per loss as on the first loss. This doesn't match real market dynamics where panic selling during a crash accelerates the decline.

**Current behavior:**
```python
effective_streak = min(max(0, streak), 10)  # Negative streaks clamped to 0
streak_multiplier = 1 + (BETA * effective_streak)  # Always 1.0 for losses
```

**Proposed change:**
```python
if effective_delta_lp > 0:
    effective_streak = min(max(0, streak), max_streak)
else:
    effective_streak = min(abs(min(0, streak)), max_streak)

streak_multiplier = 1 + (BETA_POSITIVE * effective_streak)  # for gains
# or
streak_multiplier = 1 + (BETA_NEGATIVE * effective_streak)  # for losses
```

Use a separate (lower) beta for negative streaks to keep crashes dramatic but less severe than equivalent win streaks:

```
BETA_POSITIVE = 0.10  (max 2.0x at streak 10) -- unchanged
BETA_NEGATIVE = 0.06  (max 1.6x at streak 10) -- new, milder
```

**Config knobs:**
- `pricing_beta_negative: float = 0.06`

**Example impact:**

A -20 LP loss at streak -5:
- Current: `-20 * 0.12 * 1.0 * 1.10 = -2.64`
- Proposed: `-20 * 0.12 * 1.30 * 1.10 = -3.432` (30% more severe)

At streak -10:
- Current: `-20 * 0.12 * 1.0 * 1.10 = -2.64`
- Proposed: `-20 * 0.12 * 1.60 * 1.10 = -4.224` (60% more severe)

This creates visible "crash" patterns on the price chart during loss streaks, which is exciting to watch and creates buying opportunities for users who believe the player will recover.

**Complexity:** Trivial. One config value, a few lines in `calculate_new_price`.

---

## 6. Gamba: Allow Player Selection

**Problem:** Gamba picks a random player, removing all user agency. Users can't express a thesis ("I think Player X will pop off this weekend"). The randomness makes it feel like a slot machine rather than a leveraged trade.

**Proposed options (pick one):**

**Option A -- Full choice:**
Let the user pick any tracked player (except their own linked player). Simple, maximum agency. The random hold duration still adds uncertainty.

**Option B -- Filtered shortlist:**
Present 2-3 randomly selected players. User picks from those. Keeps some randomness while allowing preference expression. Refresh the shortlist on each Gamba page visit.

**Option C -- Tiered choice:**
Picking your own choice costs more (e.g., 1.5x the cash amount) or has a lower multiplier (e.g., 2.0x instead of 2.5x). Random pick keeps the current terms. This creates a risk/reward tradeoff.

**Implementation for Option A (simplest):**
```python
# In gamba router, change from:
eligible_players = [p for p in players if p.id != user.linked_player_id]
chosen_player = random.choice(eligible_players)

# To:
if request.player_id:
    chosen_player = await session.get(TrackedPlayer, request.player_id)
    if chosen_player is None or chosen_player.id == user.linked_player_id:
        raise HTTPException(400, "Invalid player selection")
else:
    # Fallback to random for backwards compatibility
    eligible_players = [p for p in players if p.id != user.linked_player_id]
    chosen_player = random.choice(eligible_players)
```

**Frontend change:** Add a player selector dropdown to the Gamba UI, with an optional "random" button.

**Complexity:** Low for Option A. Medium for B/C due to additional UI and backend logic.

---

## 7. Auth Identity: Switch from Username to Email

**Problem:** `auth.py:70` does `WHERE username == <Remote-User header>`. If someone renames their username in Pangolin, a new user row gets created and their portfolio/balance is lost. The Remote-User header is mutable and not a stable identity key.

**Current users in the DB** (mapped by Remote-User header):
`admin@kylehub.dev`, `an.leklep`, `elinnerz`, `emil`, `fabialwe`, `firefreez3r`, `hanswarmbier`, `kate.jung`, `kolb.lukas`, `kyle`, `meru.buwumet`, `redpandaprincess`, `test@kylehub.dev`, `tobias.allgayer`

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
