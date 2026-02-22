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
P_initial = (LP_abs / 100) + 10
```

This is applied once per player (when `lp_abs == 0` and `current_price <= 10.0`). After the IPO, all subsequent updates use the dynamic formula.

Implementation: `app/pricing.py::calculate_ipo_price()`

## 3. Dynamic Price Movement

Calculates the new share price at each market update cycle.

```
P_new = P_old + (Delta_LP_abs * Alpha * (1 + Beta * |S|)) * Gamma
```

| Variable | Description | Value |
|---|---|---|
| Delta_LP_abs | Change in Absolute LP since last update | Computed per cycle |
| Alpha | Base volatility scalar | 0.15 |
| S | Streak counter (signed) | See below |
| Beta | Momentum weight | 0.1 |
| Gamma | Obfuscation factor | `gamma_base + epsilon` |

**Streak (S):** A signed integer tracking consecutive same-direction updates. Positive for consecutive LP gains, negative for consecutive losses. Resets to +1 or -1 on direction change. Resets to 0 when delta is zero. The absolute value `|S|` is used in the formula.

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

Implementation: `app/pricing.py::calculate_new_price()`, `update_streak()`

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