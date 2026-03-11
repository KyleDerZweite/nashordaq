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
P_initial = ((LP_abs / 100) + 10) * (1 + WinRatePremium + StatusPremium)
```

This is applied once per player (when `lp_abs == 0` and `current_price <= 10.0`). After the IPO, all subsequent updates use the dynamic formula.

### IPO Modifiers

- `WinRatePremium = max(0, WinRate - 0.50) * 0.40`
	- Neutral at 50% win rate.
	- Only upward pressure is applied at IPO; weak win rates do not reduce the initial listing price.
- `StatusPremium`
	- `+0.01` if Riot marks the player as `veteran`
	- `+0.02` if Riot marks the player as `freshBlood`

Implementation: `app/pricing.py::calculate_ipo_price()`

## 3. Dynamic Price Movement

Calculates the new share price at each market update cycle.

```
P_new = (P_old + (Delta_LP_abs * Alpha * StreakMultiplier) * Gamma * WinRateMultiplier) * StatusMultiplier
```

If `Delta_LP_abs == 0`, the market state is left unchanged for that cycle.

| Variable | Description | Value |
|---|---|---|
| Delta_LP_abs | Change in Absolute LP since last update | Computed per cycle |
| Alpha | Base volatility scalar | 0.15 |
| StreakMultiplier | Internal streak momentum plus Riot `hotStreak` bonus | See below |
| Gamma | Obfuscation factor | `gamma_base + epsilon` |

### League-V4 Risk Adjustments

- `WinRateMultiplier = 1 + ((WinRate - 0.50) * 0.25)`
	- High win rates slightly amplify positive and negative LP moves.
	- Low win rates slightly dampen the move size.
- `StatusMultiplier`
	- `+0.01` if `veteran`
	- `+0.02` if `freshBlood`
- `hotStreak`
	- Adds an extra `+0.15` momentum bonus on top of the internal streak multiplier.
- Flat LP cycle
	- If Riot reports the same Absolute LP as the previous refresh, Nashordaq does not change price, streak, `last_updated`, or stored price history for that cycle.

**Internal streak:** A signed integer tracking consecutive same-direction updates. Positive for consecutive LP gains and negative for consecutive losses. Resets to +1 or -1 on direction change. It is only recalculated on cycles where LP changes.

```
StreakMultiplier = 1 + (Beta * |S|) + (0.15 if hotStreak else 0)
```

**Gamma base:** Deterministic per-player value generated once from `hash(puuid) % 10000`:
```
gamma_base = 1 + ((identifier % 100) / 1000)
```
Range: [1.000, 1.099].

**Epsilon:** Random noise regenerated each update cycle:
```
epsilon = random.uniform(-0.03, 0.03)
```

**Floor:** `P_new` cannot drop below 1.00.

Implementation: `app/pricing.py::calculate_new_price()`, `calculate_win_rate()`, `update_streak()`

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

## 6. Bank Credit

Bank debt is a separate account-level liability. Borrowing adds cash immediately, but debt-adjusted net worth does not increase because the borrowed principal is offset by the new liability.

### Credit Limit

```
credit_limit = min(2500, floor_to_50((0.25 * debt_adjusted_net_worth) + 250))
```

Where:

```
debt_adjusted_net_worth = cash_balance + holdings_value + active_gamba_mark_value - outstanding_debt
```

### Interest Accrual

Outstanding debt compounds every 72 hours at 2.15%.

```
Debt_next = Debt_current + (Debt_current * 0.0215)
```

- Interest capitalizes on the full outstanding debt, including prior accrued interest.
- Repayments always clear accrued interest before principal.
- If the scheduler misses one or more rollover windows, the backend catches up one 72-hour interval at a time.

Implementation: `app/banking.py`, `app/routers/bank.py`, `app/scheduler.py`

## 7. Playing Income

Linked player accounts receive a small direct cash reward when Nashordaq detects a newly completed Ranked Solo 5v5 match for that player.

### Eligibility

- Only the user's linked Riot account is eligible.
- Only newly detected Ranked Solo 5v5 matches count.
- Each match can pay at most once.
- Matches shorter than 15 minutes are ignored so remakes and aborted games do not generate income.

### Formula

The reward uses the player's current share price after the latest market refresh.

```
PlayingIncome = P_current * BaseRate * OutcomeMultiplier
```

Current defaults:

- `BaseRate = 0.01`
- `OutcomeMultiplier = 1.0` on a win
- `OutcomeMultiplier = 0.5` on a loss

Examples:

- A player with current price `42.00` earns `0.42` on a win.
- The same player earns `0.21` on a loss.

### Processing Rules

- Match detection is driven by Riot Match-V5 history, not by win/loss snapshot deltas.
- The scheduler stores the last processed match cursor per tracked player so completed matches are not rewarded twice.
- Reward history is stored immutably for bank-summary reporting and auditability.

Implementation: `app/riot.py`, `app/scheduler.py`, `app/banking.py`, `app/routers/bank.py`

## 8. Poro Flyby Reward

Nashordaq can occasionally spawn a small clickable poro that flies across the UI and grants a flat cash reward when claimed before it leaves the screen.

### Spawn Rules

- Scheduling is per-user and server-authoritative.
- Each completed interval rolls a result between `30 minutes` and `3 hours`.
- Some intervals intentionally produce no poro.
- Only one active poro can exist per user at a time.
- Rewards can be claimed once and expire when the poro flight ends.

### Current Tier Odds And Flat Rewards

- `No spawn`: `55.0%`
- `Tier 1`: `26.0%`, reward `2`
- `Tier 2`: `11.0%`, reward `4`
- `Tier 3`: `4.5%`, reward `7`
- `Tier 4`: `2.2%`, reward `12`
- `Tier 5`: `1.0%`, reward `18`
- `Tier 6`: `0.3%`, reward `30`

### Processing Rules

- Claim validation happens on the backend, not in the browser.
- A poro claim credits cash immediately and records the change in user wealth history.
- Duplicate or expired claims are rejected.
- This mechanic is intentionally small and separate from LP-driven pricing, order execution, bank debt, and Playing Income.

Implementation: `app/poro.py`, `app/routers/poro.py`, `frontend/src/components/FlyingPoro.tsx`