# Economy Mechanics

## 1. Absolute LP Calculation

Translates a player's League of Legends rank into a continuous integer for price computation.

```
LP_abs = (T * 400) + (D * 100) + LP_current
```

| Variable | Values |
|---|---|
| T (Tier) | Iron=0, Bronze=1, Silver=2, Gold=3, Platinum=4, Emerald=5, Diamond=6, Master/Grandmaster/Challenger=7 |
| D (Division) | IV=0, III=1, II=2, I=3. Master+ uses D=3. |

Implementation: `app/pricing.py::calculate_lp_abs()`

## 2. Initial Public Offering (IPO) Price

Sets the starting share price when a player's LP data is first fetched.

```
P_initial = ((LP_abs / 100) + 10) * (1 + WinRatePremium)
```

This is applied once per player (when `lp_abs == 0` and `current_price <= 10.0`). After the IPO, all subsequent updates use the dynamic formula.

### IPO Modifiers

- `WinRatePremium = max(0, WinRate - 0.50) * 0.40`
	- Neutral at 50% win rate.
	- Only upward pressure is applied at IPO; weak win rates do not reduce the initial listing price.

Implementation: `app/pricing.py::calculate_ipo_price()`

## 3. Dynamic Price Movement

Calculates the new share price at each market update cycle.

```
EffectiveDeltaLP =
	Delta_LP_abs                              if -24 <= Delta_LP_abs <= 20
	20 + ((Delta_LP_abs - 20) * 0.25)        if Delta_LP_abs > 20
	-24 + ((Delta_LP_abs + 24) * 0.50)       if Delta_LP_abs < -24

GainDampener (only applied when EffectiveDeltaLP > 0):
	clamp(AvgLpLossOnLoss / AvgLpGainOnWin, 0.3, 1.0)  if both averages known
	clamp((AvgLpGainOnWin - 5) / AvgLpGainOnWin, 0.3, 1.0)  if only gain known
	clamp(AvgLpLossOnLoss / (AvgLpLossOnLoss + 5), 0.3, 1.0)  if only loss known
	0.85  if neither average is known

EffectiveDeltaLP = EffectiveDeltaLP * GainDampener   (positive moves only)

EffectiveStreak = min(max(S, 0), 10)
StreakMultiplier = 1 + (Beta * EffectiveStreak)

PriceDelta = EffectiveDeltaLP * Alpha * StreakMultiplier
PriceDelta = PriceDelta * 1.10 if EffectiveDeltaLP < 0 else PriceDelta
P_new = P_old + PriceDelta
```

If `Delta_LP_abs == 0` and no new matches are detected, the market state is left unchanged for that cycle.

| Variable | Description | Value |
|---|---|---|
| Delta_LP_abs | Change in Absolute LP since last update | Computed per cycle |
| Alpha | Base volatility scalar | 0.12 |
| StreakMultiplier | Internal streak momentum | See below |
| GainDampener | LP ratio scalar applied to positive moves only | `clamp(loss/win, 0.3, 1.0)` or `0.85` default |

### Per-Match Pricing

Price updates are applied per-match rather than per-poll when individual games are detected between LP snapshots. This produces accurate per-game streaks and a complete audit trail.

Each scheduler cycle:
1. Polls `league-v4/entries/by-puuid` for the LP snapshot.
2. Fetches match history via `match-v5` (shared with the playing income pipeline).
3. Correlates the LP delta with detected matches and attributes LP to each game.
4. Applies `update_streak` + `calculate_new_price` once per match in chronological order.

**LP attribution logic:**
- **Single match (most common):** The entire LP delta is attributed to that match. Source: `OBSERVED`.
- **Multiple matches, same direction:** LP is split evenly across games. Source: `ESTIMATED`.
- **Multiple matches, mixed direction:** Uses stored LP averages (or `20 LP` default) to split proportionally between wins and losses, scaled to match the total delta.
- **No matches with LP change:** Falls back to aggregate pricing (one update with the total delta). This covers promotion/demotion LP adjustments.

Each attributed match produces a `PlayerMatch` row storing `lp_before`, `lp_after`, `lp_delta`, `lp_delta_source`, `streak_before`, `streak_after`, `price_before`, and `price_after`. This enables deterministic price recalculation from stored data.

### League-V4 Risk Adjustments

- LP efficiency taper
	- The first `+20 LP` of a positive refresh count at full strength; additional LP only count at `25%` efficiency.
	- The first `-24 LP` of a negative refresh count at full strength; additional LP only count at `50%` efficiency.
- Negative LP bias
	- Negative refreshes are multiplied by `1.10` after the LP efficiency taper, so losses hit a bit harder than similarly sized gains.
- LP gain dampener
	- Applied only to positive LP moves (gains). Losses are not dampened.
	- `AvgLpLossOnLoss / AvgLpGainOnWin` is clamped to `[0.3, 1.0]`.
	- If only one average is available, the missing one is bootstrapped with a `5 LP` offset (loss = gain - 5, or gain = loss + 5).
	- If neither average is available, the dampener defaults to `0.85`.
	- The scheduler persists rolling LP averages per tracked player using an EMA (`alpha = 0.35` default).
	- Samples are learned from pure refresh directions only:
		- Wins-only refresh (`wins` increased, `losses` unchanged, `Delta_LP_abs > 0`) updates `AvgLpGainOnWin`.
		- Losses-only refresh (`losses` increased, `wins` unchanged, `Delta_LP_abs < 0`) updates `AvgLpLossOnLoss`.
	- Mixed or ambiguous refreshes still update snapshot counters but do not create LP-per-win/loss samples.
- Low-price loss dampening
	- When a stock's price is below `pricing_low_price_threshold` (default `15.0 P`), negative price moves are scaled by `price / threshold`.
	- This caps the percentage loss at the threshold-level rate, preventing low-priced stocks from spiraling into the floor.
	- Gains are not dampened; low-priced stocks recover at full speed.
- Flat LP cycle
	- If Riot reports the same Absolute LP as the previous refresh and no new matches are detected, Nashordaq does not change price, streak, `last_updated`, or stored price history for that cycle.

**Internal streak:** A signed integer tracking consecutive same-direction updates. Positive for consecutive LP gains and negative for consecutive losses. Resets to +1 or -1 on direction change, and is capped at `+10` / `-10`. It is only recalculated on cycles where LP changes. Both positive and negative streaks contribute to price momentum, using separate beta coefficients: `BETA = 0.10` for win streaks (max 2.0x at streak 10) and `pricing_beta_negative = 0.06` for loss streaks (max 1.6x at streak 10). The milder negative beta creates visible crash patterns during loss streaks without being as punishing as equivalent win-streak bonuses.

**Floor:** `P_new` cannot drop below 1.00.

### Inactivity Pressure

When a tracked player has had no LP change for a configurable duration, the price decays toward the IPO price (the price the player would receive if listed fresh with their current LP and win rate) each scheduler cycle.

```
FairValue = IPO_Price(LP_abs, WinRate)
PriceDiff = P_current - FairValue
P_new = P_current - (PriceDiff * DecayRate)
```

- Decay only starts after `48` hours (default) without an LP change.
- A player priced above fair value drifts down; a player priced below fair value drifts up.
- The moment LP changes again, normal pricing resumes.
- The decay rate is time-based (per hour), scaled by the actual scheduler cycle interval. This keeps decay speed consistent regardless of how many players are tracked.

Current defaults:

- `pricing_inactivity_threshold_hours = 48.0`
- `pricing_inactivity_decay_rate_per_hour = 0.00075`

Implementation: `app/scheduler.py::market_update_job()` (inactivity branch)

Implementation: `app/pricing.py::calculate_new_price()`, `calculate_win_rate()`, `update_streak()`, `app/scheduler.py::_learn_player_lp_averages()`, `_attribute_lp_to_matches()`, `_apply_per_match_price_updates()`

## 4. Immediate Execution + Market Impact

Orders execute immediately with market impact: buying pushes the price up, selling pushes it down. The impact is proportional to order size.

### Market Impact

Each trade moves the market price based on a configurable liquidity depth parameter:

```
impact_pct = quantity / liquidity_depth

BUY:
  avg_execution_price = P * (1 + impact_pct / 2)
  new_market_price    = P * (1 + impact_pct)

SELL:
  avg_execution_price = P * (1 - impact_pct / 2)
  new_market_price    = max(P * (1 - impact_pct), 1.0)
```

The buyer/seller pays/receives the average price across the impact ramp (the `/ 2` midpoint), not the pre-trade or post-trade price. The market price updates to the post-trade level for all subsequent viewers.

Current default: `market_impact_liquidity_depth = 1000`

| Order Size | Impact % | Avg Slippage |
|---|---|---|
| 5 shares | 0.5% | 0.25% |
| 10 shares | 1% | 0.5% |
| 50 shares | 5% | 2.5% |
| 100 shares | 10% | 5% |
| 300 shares | 30% | 15% |

A round-trip (buy then sell the same quantity) always loses money to slippage. The only way to profit is if LP-driven price movement exceeds the round-trip cost.

Order splitting does not help: each sub-order moves the price, and subsequent sub-orders face the moved price. Due to compounding, splitting is slightly more expensive than a single large order.

**Exemptions:** Gamba (system-generated) orders do not apply market impact. Only `MANUAL` source orders move the market.

Each trade records a `PriceHistory` row so the price chart reflects trade-driven movements.

### Minimum Holding Period

After buying shares, those shares cannot be sold for a configurable period (default: 4 hours). The lock is per-lot (FIFO): buying 10 shares at 09:00 and 10 more at 11:00 means the first batch unlocks at 13:00, the second at 15:00.

### Buy Revert Grace Period

- Executed BUY orders can be reverted via order cancellation during a short grace window (default: 120 seconds).
- Revert refunds exactly `execution_price * quantity` and reverses the market impact (price is pushed back down).
- Revert is only allowed if shares from that BUY lot were not sold yet.
- Reverted orders are marked with status `REVERTED`.

Implementation: `app/pricing.py::calculate_market_impact()`, `app/routers/orders.py::place_order()`

## 5. Order Validation at Placement

Orders are validated and executed in the same request.

- **BUY:** `avg_execution_price * quantity` (including market impact) must not exceed user balance.
- **SELL:** Available shares must be sufficient.

## 6. Bank Failsafe

Bank debt is now a rescue-only account-level liability. Players do not get a general credit line anymore.

### Rescue Unlock

The bank offers a fixed failsafe package only when debt-adjusted net worth is low enough, the player has no existing debt, and they still have a rescue use available.

```
debt_adjusted_net_worth = cash_balance + holdings_value + active_gamba_mark_value - outstanding_debt
```

- `active_gamba_mark_value` is the sum of `cash_amount` of all active Gamba positions. It represents the value "locked" in those positions.

Current defaults:

- Rescue unlock threshold: `250 P` debt-adjusted net worth or below
- Rescue amount: `750 P`
- Rescue cannot be claimed while any debt is still outstanding
- Rescue starts with `1` lifetime use; after that, an admin must restore access before it can be claimed again

### Interest Accrual

Rescue debt uses a flat `2.0%` interest rate every `120` hours.

```
Debt_next = Debt_current + (Debt_current * 0.02)
```

- Claiming the failsafe adds cash immediately and also adds an immediate one-time `2.0%` opening charge on the `750 P` rescue amount.
- Interest capitalizes on the full outstanding debt, including prior accrued interest.
- Repayments always clear accrued interest before principal.
- If the scheduler misses one or more rollover windows, the backend catches up one `120`-hour interval at a time.

Implementation: `app/banking.py`, `app/routers/bank.py`, `app/scheduler.py`

## 7. Gamba (Long-Term Leveraged Positions)

Users can choose to enter a "Gamba" position, which is a leveraged long-term investment in a randomly selected tracked player (excluding their own linked player).

### Placement

- User invests a fixed `cash_amount`.
- A random eligible player is chosen.
- A hold duration is randomly selected between `24` and `168` hours.
- A virtual `quantity` of shares is bought at the player's current price.
- Cash is deducted immediately.

### Settlement

- After the hold duration expires, the position is automatically settled by the scheduler.
- The "Raw P&L" is calculated as `(current_price * quantity) - initial_cash_amount`.
- The settled payout is `initial_cash_amount + (raw_pnl * multiplier)`.
- The multiplier scales linearly with the randomly drawn hold duration: shorter holds get a lower multiplier, longer holds get a higher one. This makes longer holds feel rewarding rather than purely punishing.
- `multiplier = min + (hold_hours - min_hold) / (max_hold - min_hold) * (max - min)`
- Default range: `2.0x` at 24h hold to `4.0x` at 168h hold.
- The payout is credited to the user's cash balance.
- Payout cannot drop below `0.0`.

Implementation: `app/routers/gamba.py`, `app/scheduler.py`

## 8. Playing Income

Linked player accounts receive a small direct cash reward when Nashordaq detects a newly completed Ranked Solo 5v5 match for that player.

### Eligibility

- Only the user's linked Riot account is eligible.
- Only newly detected Ranked Solo 5v5 matches count.
- Each match can pay at most once.
- Matches shorter than 15 minutes are ignored so remakes and aborted games do not generate income.

### Formula

The reward uses the player's current share price after the latest market refresh, with no cap. Instead of a minimum payout, a flat BasePayout is always paid, plus a variable component based on share price.

```
PlayingIncome = BasePayout + (P_current * BaseRate * OutcomeMultiplier * DailyTierMultiplier)
```

Current defaults:

- `BasePayout = 0.50` on a win
- `BasePayout = 0.25` on a loss
- `BaseRate = 0.01`
- `OutcomeMultiplier = 1.0` on a win
- `OutcomeMultiplier = 0.50` on all losses
- `DailyTierMultiplier = 1.00` for games `1` to `3` that day
- `DailyTierMultiplier = 0.65` from game `4` onward that day

Examples:

- A player with current price `42.00` earns `0.50 + (42.00 * 0.01 * 1.0 * 1.0) = 0.92` on their first win of the day.
- The same player earns `0.25 + (42.00 * 0.01 * 0.5 * 1.0) = 0.46` on their first loss of the day.
- A low-priced player still earns at least `0.50` for an early win and `0.25` for an early loss.
- After three rewarded matches in a day, later games still pay out, but at `65%` of the variable component.

### Processing Rules

- Match detection is driven by Riot Match-V5 history, not by win/loss snapshot deltas.
- The scheduler backfills from a configured `playing_income_start_date` and paginates through all Ranked Solo matches since that point.
- Reward deduplication is based on immutable `playing_income_entries`, so a stale cursor cannot silently skip unpaid matches.
- The last processed match cursor is still stored per tracked player for observability, but it is no longer the sole source of truth for payouts.
- Reward history is stored immutably for bank-summary reporting and auditability.

Implementation: `app/riot.py`, `app/scheduler.py`, `app/banking.py`, `app/routers/bank.py`

## 8. Poro Flyby Reward

Nashordaq can occasionally spawn a small clickable poro that flies across the UI and grants a flat cash reward when claimed before it leaves the screen.

### Spawn Rules

- Scheduling is per-user and server-authoritative.
- Each completed interval rolls a result between `13 minutes` and `75 minutes`.
- Some intervals intentionally produce no poro.
- Only one active poro can exist per user at a time.
- Rewards can be claimed once and expire when the poro flight ends.
- Poro paths only cross between adjacent screen edges, so they do not traverse the full screen from `left` to `right` or `top` to `bottom`.
- Default flight time is shorter, usually between `6` and `10` seconds, to keep claims more reactive.

### Current Tier Odds And Flat Rewards

- `No spawn`: `69.1628%`
- `Tier 1`: `12.5%`, reward `8`
- `Tier 2`: `7.6923%`, reward `13`
- `Tier 3`: `4.7619%`, reward `21`
- `Tier 4`: `2.9412%`, reward `34`
- `Tier 5`: `1.8182%`, reward `55`
- `Tier 6`: `1.1236%`, reward `89`

This table uses `1 / reward` as the spawn probability for each reward tier, with the remainder allocated to `No spawn`. That yields an average payout of about `6.0` per roll, including `No spawn` outcomes.

### Processing Rules

- Claim validation happens on the backend, not in the browser.
- Claim requests must include the user's click coordinates (normalized viewport fraction). The backend validates the click is within tolerance of the poro's server-computed position at claim time. This prevents automated claiming via SSE stream listeners.
- A poro claim credits cash immediately and records the change in user wealth history.
- Duplicate or expired claims are rejected.
- This mechanic is intentionally separate from LP-driven pricing, order execution, bank debt, and Playing Income.

Implementation: `app/poro.py`, `app/routers/poro.py`, `frontend/src/components/FlyingPoro.tsx`