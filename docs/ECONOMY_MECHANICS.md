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

## 4. Forward Pricing

Prevents front-running by decoupling order placement from execution.

1. User submits a buy or sell order via the API.
2. Order is saved to the database with status `PENDING`.
3. The scheduler job runs at the configured interval (default: 30 minutes).
4. The job fetches current LP data from the Riot API and calculates `P_new` for all tracked players.
5. The job processes all `PENDING` orders in FIFO order (`created_at` ascending) using the newly calculated prices.
6. For each order:
   - **BUY:** If `user.balance >= price * quantity`, deduct balance and add shares. Otherwise, cancel.
   - **SELL:** If `holding.quantity >= order.quantity`, remove shares and credit balance. Otherwise, cancel.
7. Executed orders are marked `EXECUTED` with the fill price recorded. A `Transaction` record is created.
8. All price updates, order executions, and balance changes are committed in a single atomic database transaction.

Implementation: `app/scheduler.py::market_update_job()`

## 5. Order Validation at Placement

Orders are validated at placement time as a sanity check, but the binding validation occurs at execution.

- **BUY:** Estimated cost (`current_price * quantity`) must not exceed user balance. This is advisory; the actual execution price may differ.
- **SELL:** Available shares (`owned - sum(pending_sell_quantities)`) must be sufficient. Pending sell orders reduce available shares to prevent overselling.