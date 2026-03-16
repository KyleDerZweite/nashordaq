# Market Simulation Lab

The Simulation Lab is an admin-only tool for exploring how pricing parameter changes affect share price trajectories. It runs the same pricing formula used in production but lets you override any parameter and compare results side by side -- without touching real market state.

## Access

1. Log in as an admin user.
2. Open the user menu (top-right initial button).
3. Click **Simulation Lab**.
4. Click **Back to Market** to return to the normal view.

The simulation view replaces the main content area while active. It does not affect the live market, orders, or any other state.

## Concepts

### Scenario Modes

The simulator needs a sequence of matches (LP deltas) to process. There are two ways to provide them:

**Synthetic** -- Type a comma-separated list of LP deltas directly. Positive values are wins, negative values are losses. Example: `20, 18, -15, 22, -20, -18, -16, 25, 20, -14`. You also set the starting price and starting streak manually. This mode is useful for testing specific edge cases ("what happens after 5 consecutive +30 LP wins?") or exploring hypothetical sequences.

**Replay** -- Select a tracked player from the dropdown. The simulator fetches that player's entire `PlayerMatch` history and replays it from the first recorded match. Starting price and streak are taken from the first match in the database. This mode shows how a player's actual match history would have played out under different pricing parameters.

### Parameter Sets

Each simulation run processes the match sequence through two independent parameter sets, labeled **Baseline** and **Comparison**. Both start with the server's current production defaults (fetched from `GET /api/simulate/defaults`). You can then edit any parameter in either set.

When you leave a field empty, the server fills it with the current production default. This means you only need to change the parameters you want to test.

The eight configurable parameters and what they control:

| Parameter | Description | Production Default |
|---|---|---|
| Alpha (base volatility) | Scales every price move. Higher = more volatile market. | `0.12` |
| Loss move multiplier | Extra multiplier applied only to negative price moves. `1.10` means losses hit 10% harder than equivalent gains. | `1.10` |
| Max effective streak | Cap on how high the streak multiplier can go. Does not cap the internal streak counter, just its effect on price. | `10` |
| Positive LP soft cap | LP gains above this threshold have reduced efficiency. | `20` |
| Negative LP soft cap | LP losses beyond this threshold have reduced efficiency. | `24` |
| Positive LP excess efficiency | How much of the LP above the positive soft cap actually counts. `0.25` = 25% efficiency on excess. | `0.25` |
| Negative LP excess efficiency | How much of the LP beyond the negative soft cap actually counts. `0.50` = 50% efficiency on excess. | `0.50` |
| Gain dampener default | Scalar applied only to positive effective LP. Reduces upward moves to keep prices from inflating too fast. Production uses a dynamic ratio based on per-player LP averages, but the simulation uses this fixed default. | `0.85` |

For full formula details, see [ECONOMY_MECHANICS.md](ECONOMY_MECHANICS.md) section 3.

### Simulation Output

After clicking **Run Simulation**, results appear in two tabs:

**Chart** -- An overlay line chart showing the price trajectory for each parameter set. The baseline is drawn as a solid gold line; the comparison as a dashed cyan line. Hover over any point to see the match number, LP delta, and win/loss status.

**Step Data** -- A per-match table showing every intermediate value the pricing engine computed. Use the set selector buttons at the top to switch between Baseline and Comparison data.

| Column | Meaning |
|---|---|
| # | Match number (1-indexed) |
| LP | Raw LP delta for this match |
| W/L | Win or Loss |
| Streak | Streak value before and after this match |
| Eff LP | Effective LP after soft cap taper and gain dampener |
| Streak Mult | `1 + (0.1 * EffectiveStreak)` |
| Price Before | Share price entering this match |
| Price After | Share price after this match's move |
| Move | `Price After - Price Before` |

## Typical Workflows

### "What if alpha was higher?"

1. Switch to **Synthetic** mode.
2. Enter a representative sequence (or use the default).
3. Leave Baseline at production defaults.
4. In Comparison, change **Alpha** to `0.15`.
5. Click **Run Simulation**.
6. Compare the chart to see how much more volatile the comparison trajectory is.

### "How would this player's history look with a different loss multiplier?"

1. Switch to **Replay** mode.
2. Select the player.
3. Leave Baseline at defaults.
4. In Comparison, change **Loss move multiplier** to `1.25`.
5. Click **Run Simulation**.
6. Switch to the **Step Data** tab and toggle between Baseline and Comparison to see exactly where the trajectories diverge.

### "Is the gain dampener too aggressive?"

1. Use **Replay** mode with a player who has many wins.
2. Set Comparison's **Gain dampener default** to `1.0` (no dampening).
3. Run and compare -- the Comparison line will show how much higher prices would go without the dampener.

## API Reference

The simulation backend lives at `/api/simulate` and does not require admin auth (it is read-only and stateless). Three endpoints:

### `GET /api/simulate/defaults`

Returns the current production pricing parameters. The frontend uses this to pre-fill the parameter editor inputs.

```json
{
  "pricing_alpha": 0.12,
  "pricing_loss_move_multiplier": 1.10,
  "pricing_max_effective_streak": 10,
  "pricing_positive_lp_soft_cap": 20,
  "pricing_negative_lp_soft_cap": 24,
  "pricing_positive_lp_excess_efficiency": 0.25,
  "pricing_negative_lp_excess_efficiency": 0.50,
  "pricing_win_streak_lp_ratio_default": 0.85
}
```

### `GET /api/simulate/players/{player_id}/matches`

Returns the full `PlayerMatch` history for a tracked player, ordered chronologically. Each entry includes the LP delta, streak state, and price state before/after. Used by the frontend to show match count in Replay mode.

### `POST /api/simulate`

Runs one or more simulation trajectories. Provide either `matches` (synthetic) or `player_id` (replay), plus one or more `parameter_sets`.

**Synthetic request:**

```json
{
  "matches": [
    { "delta_lp": 20, "win": true },
    { "delta_lp": -15, "win": false }
  ],
  "starting_price": 25.0,
  "starting_streak": 0,
  "parameter_sets": [
    { "label": "Baseline" },
    { "label": "Comparison", "pricing_alpha": 0.15 }
  ]
}
```

**Replay request:**

```json
{
  "player_id": 3,
  "starting_price": 25.0,
  "starting_streak": 0,
  "parameter_sets": [
    { "label": "Baseline" },
    { "label": "Comparison", "pricing_loss_move_multiplier": 1.25 }
  ]
}
```

When using `player_id`, the server overrides `starting_price` and `starting_streak` with the values from the player's first recorded match.

**Constraints:**
- Cannot provide both `matches` and `player_id`.
- Maximum 500 matches per simulation.

**Response:** An array of trajectories, one per parameter set. Each trajectory contains the resolved parameters and a step-by-step breakdown.

## Implementation

| Layer | Files |
|---|---|
| Backend router | `backend/app/routers/simulation.py` |
| Pydantic schemas | `backend/app/schemas.py` (Simulation* types) |
| Frontend view | `frontend/src/components/SimulationView.tsx` |
| API hooks | `frontend/src/api/hooks.ts` (`useSimulationDefaults`, `useSimulationPlayerMatches`, `useRunSimulation`) |
| TypeScript types | `frontend/src/types.ts` (Simulation* interfaces) |
| App wiring | `frontend/src/App.tsx` (state + conditional render), `frontend/src/components/Header.tsx` (menu button) |

The simulation engine reimplements the pricing formula independently from `app/pricing.py` so that each parameter set can use its own overrides without mutating global settings. The formulas are identical; see `_lp_efficiency`, `_update_streak`, and `_compute_step` in `simulation.py`.
