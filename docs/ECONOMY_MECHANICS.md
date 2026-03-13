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

EffectiveStreak = min(max(S, 0), 10)
StreakMultiplier = 1 + (Beta * EffectiveStreak)

OutcomeBalanceFactor = clamp(AvgLpLossOnLoss / AvgLpGainOnWin, 0.25, 1.0)
OutcomeBalanceFactor = 1.0 when averages are unavailable

PriceDelta = EffectiveDeltaLP * Alpha * StreakMultiplier * OutcomeBalanceFactor
PriceDelta = PriceDelta * 1.10 if EffectiveDeltaLP < 0 else PriceDelta
P_new = P_old + PriceDelta
```

If `Delta_LP_abs == 0`, the market state is left unchanged for that cycle.

| Variable | Description | Value |
|---|---|---|
| Delta_LP_abs | Change in Absolute LP since last update | Computed per cycle |
| Alpha | Base volatility scalar | 0.12 |
| StreakMultiplier | Internal streak momentum scaled by LP loss/win ratio factor | See below |
| OutcomeBalanceFactor | LP-per-loss vs LP-per-win balancing factor | `clamp(loss/win, 0.25, 1.0)` |

### League-V4 Risk Adjustments

- LP efficiency taper
	- The first `+20 LP` of a positive refresh count at full strength; additional LP only count at `25%` efficiency.
	- The first `-24 LP` of a negative refresh count at full strength; additional LP only count at `50%` efficiency.
- Negative LP bias
	- Negative refreshes are multiplied by `1.10` after the LP efficiency taper, so losses hit a bit harder than similarly sized gains.
- LP outcome balance factor
	- `AvgLpLossOnLoss / AvgLpGainOnWin` is clamped to `[0.25, 1.0]` and applied to the full LP move.
	- If these average values are unavailable, the factor defaults to `1.0`.
	- The scheduler persists rolling LP averages per tracked player using an EMA (`alpha = 0.35` default).
	- Samples are learned from pure refresh directions only:
		- Wins-only refresh (`wins` increased, `losses` unchanged, `Delta_LP_abs > 0`) updates `AvgLpGainOnWin`.
		- Losses-only refresh (`losses` increased, `wins` unchanged, `Delta_LP_abs < 0`) updates `AvgLpLossOnLoss`.
	- Mixed or ambiguous refreshes still update snapshot counters but do not create LP-per-win/loss samples.
- Flat LP cycle
	- If Riot reports the same Absolute LP as the previous refresh, Nashordaq does not change price, streak, `last_updated`, or stored price history for that cycle.

**Internal streak:** A signed integer tracking consecutive same-direction updates. Positive for consecutive LP gains and negative for consecutive losses. Resets to +1 or -1 on direction change, and is capped at `+10` / `-10`. It is only recalculated on cycles where LP changes. Only positive streak contributes to price momentum.

```
OutcomeBalanceFactor = clamp(AvgLpLossOnLoss / AvgLpGainOnWin, 0.25, 1.0)
OutcomeBalanceFactor = 1.0 when averages are unavailable
EffectiveStreak = min(max(S, 0), 10)
StreakMultiplier = 1 + (Beta * EffectiveStreak)

EffectiveDeltaLP =
	Delta_LP_abs                              if -24 <= Delta_LP_abs <= 20
	20 + ((Delta_LP_abs - 20) * 0.25)        if Delta_LP_abs > 20
	-24 + ((Delta_LP_abs + 24) * 0.50)       if Delta_LP_abs < -24

PriceDelta = EffectiveDeltaLP * Alpha * StreakMultiplier * OutcomeBalanceFactor
PriceDelta = PriceDelta * 1.10 if EffectiveDeltaLP < 0 else PriceDelta
```

**Floor:** `P_new` cannot drop below 1.00.

Implementation: `app/pricing.py::calculate_new_price()`, `calculate_win_rate()`, `update_streak()`, `app/scheduler.py::_learn_player_lp_averages()`

## 4. Immediate Execution + Holding Adjustment

Orders execute immediately at the currently visible market price.

1. User submits a buy or sell order via the API.
2. Order is executed immediately and stored with status `EXECUTED`.
3. **BUY:** User balance is deducted at execution and shares are added instantly.
4. **SELL:** Shares are removed instantly and proceeds are calculated with a holding-duration multiplier per consumed lot (FIFO lots).
5. Every execution writes a `Transaction` row.

### Buy Revert Grace Period

- Executed BUY orders can be reverted via order cancellation during a short grace window (default: 60 seconds).
- Revert refunds exactly `execution_price * quantity`.
- Revert is only allowed if shares from that BUY lot were not sold yet.
- Reverted orders are marked with status `REVERTED`.

Sell multiplier defaults:

- Hold `< 6h`: short-hold fee ramps from `-2%` (at 0h) to `0%` (at 6h).
- Hold `6h` to `< 12h`: no adjustment.
- Hold `>= 12h`: `+2%` long-hold bonus.

Implementation: `app/routers/orders.py::place_order()`, `app/pricing.py::calculate_sell_multiplier()`

## 5. Order Validation at Placement

Orders are validated and executed in the same request.

- **BUY:** `current_price * quantity` must not exceed user balance.
- **SELL:** Available shares must be sufficient.

## 6. Bank Failsafe

Bank debt is now a rescue-only account-level liability. Players do not get a general credit line anymore.

### Rescue Unlock

The bank offers a fixed failsafe package only when debt-adjusted net worth is low enough, the player has no existing debt, and they still have a rescue use available.

```
debt_adjusted_net_worth = cash_balance + holdings_value + active_gamba_mark_value - outstanding_debt
```

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

## 7. Playing Income

Linked player accounts receive a small direct cash reward when Nashordaq detects a newly completed Ranked Solo 5v5 match for that player.

### Eligibility

- Only the user's linked Riot account is eligible.
- Only newly detected Ranked Solo 5v5 matches count.
- Each match can pay at most once.
- Matches shorter than 15 minutes are ignored so remakes and aborted games do not generate income.

### Formula

The reward uses the player's current share price after the latest market refresh, but caps the price input so already-expensive accounts do not snowball the cash faucet.

```
PlayingIncome = max(MinimumPayout, min(P_current, PriceCap) * BaseRate * OutcomeMultiplier) * DailyTierMultiplier
```

Current defaults:

- `BaseRate = 0.0125`
- `PriceCap = 35`
- `MinimumPayout = 0.20` on a win
- `MinimumPayout = 0.10` on a loss
- `OutcomeMultiplier = 1.0` on a win
- `OutcomeMultiplier = 0.50` on all losses
- `DailyTierMultiplier = 1.00` for games `1` to `3` that day
- `DailyTierMultiplier = 0.65` from game `4` onward that day

Examples:

- A player with current price `42.00` is capped to `35.00` for this calculation and earns `0.44` on their first win of the day.
- The same player earns `0.22` on their first loss of the day.
- A low-priced player still earns at least `0.20` for an early win and `0.10` for an early loss.
- After three rewarded matches in a day, later games still pay out, but at `65%` of the early-game payout.

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
- Each completed interval rolls a result between `20 minutes` and `2 hours`.
- Some intervals intentionally produce no poro.
- Only one active poro can exist per user at a time.
- Rewards can be claimed once and expire when the poro flight ends.
- Poro paths only cross between adjacent screen edges, so they do not traverse the full screen from `left` to `right` or `top` to `bottom`.
- Default flight time is shorter, usually between `6` and `10` seconds, to keep claims more reactive.

### Current Tier Odds And Flat Rewards

- `No spawn`: `50.2864%`
- `Tier 1`: `20.0%`, reward `5`
- `Tier 2`: `12.5%`, reward `8`
- `Tier 3`: `7.6923%`, reward `13`
- `Tier 4`: `4.7619%`, reward `21`
- `Tier 5`: `2.9412%`, reward `34`
- `Tier 6`: `1.8182%`, reward `55`

This table uses `1 / reward` as the spawn probability for each reward tier, with the remainder allocated to `No spawn`. That yields an average payout of about `6.0` per roll, including `No spawn` outcomes.

### Processing Rules

- Claim validation happens on the backend, not in the browser.
- A poro claim credits cash immediately and records the change in user wealth history.
- Duplicate or expired claims are rejected.
- This mechanic is intentionally separate from LP-driven pricing, order execution, bank debt, and Playing Income.

Implementation: `app/poro.py`, `app/routers/poro.py`, `frontend/src/components/FlyingPoro.tsx`