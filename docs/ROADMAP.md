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

## Next Up

### SECURITY: Poro Auto-Claim Bot Vulnerability

**Severity:** Critical. The poro claim system is trivially automatable via browser JS.

**Problem:** The SSE stream (`/api/poro/stream`) pushes `active_spawn` including `spawn_id` the instant a poro spawns. The claim endpoint (`POST /api/poro/claim`) only requires `spawn_id` — no proof of interaction. A user can paste ~5 lines of JS into their browser console to claim every poro within milliseconds of spawning with 100% success rate, bypassing the intended gameplay entirely.

```js
// exploit — claims every poro automatically
const es = new EventSource("/api/poro/stream");
es.onmessage = async (e) => {
  const data = JSON.parse(e.data);
  if (data.active_spawn?.spawn_id) {
    await fetch("/api/poro/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spawn_id: data.active_spawn.spawn_id }),
    });
  }
};
```

**Fix plan (click-coordinate validation):**

1. Extend `PoroClaimRequest` schema with optional `click_x` and `click_y` (float, 0-1 range, fraction of viewport).
2. In `claim_poro_spawn`, after existing validation, compute the poro's position at claim time using `spawned_at`, `expires_at`, `start_x/y`, `end_x/y`. Reject if the click position is more than 0.15 (15% of viewport) from the actual poro position.
3. Make `click_x`/`click_y` required after a grace period (or immediately since the frontend already has this data).
4. Frontend: pass the click event's normalized viewport position in the claim request.
5. Optional hardening: add a short-lived nonce (obtained from `GET /api/poro`) that must be included in the claim, to prevent stale claims and add a round-trip cost.

**Why this approach:** The server already knows the poro's exact position at every millisecond (it has `spawned_at`, `expires_at`, `start/end x/y`). Requiring the click position is a zero-cost UX change that completely defeats the listener-based exploit. A determined attacker could reverse-engineer the position math, but that raises the bar significantly from "paste 5 lines of JS."

**Files to modify:**
- `backend/app/schemas.py` — add `click_x`, `click_y` to `PoroClaimRequest`
- `backend/app/poro.py` — add position validation in `claim_poro_spawn`
- `frontend/src/components/FlyingPoro.tsx` — pass click coordinates to claim mutation

---

### 8. Built-In Auth Mode

Add a self-contained authentication layer so the app can run standalone without any reverse proxy or external auth provider. This is the default for self-hosters who just want `docker compose up`.

**Two auth modes, auto-detected:**

- `proxy` - current behavior. Reads `Remote-Email` / `Remote-Name` headers injected by a reverse proxy (Pangolin, Authelia, Caddy forward_auth, etc.). Unchanged.
- `builtin` - the app handles registration, login, and sessions directly. No proxy required.

The mode is configured via `NASHORDAQ_AUTH_MODE` (default: `builtin`). When both are available (proxy headers present AND a builtin session exists), proxy headers take precedence.

**Registration flow (builtin mode):**

1. User visits the app, sees a registration/login page.
2. Registration collects: email, display name, password, game name, tag line.
3. Backend creates the `User`, hashes the password, resolves the Riot PUUID, creates the `TrackedPlayer`, and links them - combining current auto-provisioning and onboarding into one step.
4. Login via email + password returns a signed session cookie.

**Implementation notes:**

- Password hashing: argon2id (via `argon2-cffi`).
- Sessions: signed cookies using a `NASHORDAQ_SECRET_KEY` env var.
- New columns on `User`: `password_hash` (nullable, only set in builtin mode).
- The existing `_get_current_user` dependency in `auth.py` gains a second code path: check session cookie if no proxy headers are present.
- Frontend: a login/register page that only renders when `auth_mode == builtin` (detected via a public `/api/auth/info` endpoint).

**What this enables:**

- `docker compose up` with just `NASHORDAQ_RIOT_API_KEY` and `NASHORDAQ_SECRET_KEY` gives a working instance. No Zitadel, no Pangolin, no reverse proxy.
- Self-hosters who prefer an IAP can set `NASHORDAQ_AUTH_MODE=proxy` and use their existing setup.
- The maintainer's own deployment continues using Pangolin exactly as it does today.

### 9. Gamba Feature Flag

Gate all Gamba functionality behind `NASHORDAQ_GAMBA_ENABLED` (default: `true`).

- Backend: Gamba router returns 404 when disabled. Scheduler skips Gamba settlement.
- Frontend: Gamba UI elements hidden when the flag is off (exposed via a public `/api/config` or similar endpoint).
- No code removal. The feature stays in the codebase, just gated at runtime.

This is required for any future Riot-compliant public deployment (Riot's developer policies prohibit gambling mechanics), but is also good hygiene - operators should be able to disable features they don't want.

---

## Future (v2+)

The items below are not on the current roadmap. They are documented for reference and should only be pursued after demand is proven.

### Distribution Strategy

**Primary model: self-hosted open source (single-tenant).**

Each friend group runs their own instance with their own Riot Personal API key. One instance = one friend group = one market. This is the standard self-hosted software model (same as Jellyfin, Gitea, Uptime Kuma, etc.) and does not violate any Riot policies.

- Personal API keys are free and instant to obtain at developer.riotgames.com.
- Rate limit (100 req/2min) is sufficient for 5-50 tracked players.
- Each instance is independent. This is NOT the "BYOK" violation Riot prohibits (that refers to one application pooling multiple keys).
- Gamba is fine on private instances - Riot's developer policies apply to applications submitted for Production key review, not to private deployments.
- The built-in auth mode (item 8) removes the need for any external auth stack, making deployment trivial.

**Secondary model (only if demand proves it): centralized hosting.**

A single public instance serving multiple groups. This requires a Riot Production API key (30,000 req/10min), multi-room architecture, and Riot policy compliance (no Gamba, no gambling terminology). Only pursue if self-hosted adoption demonstrates real demand and people explicitly ask for a hosted alternative.

Production key application requires: working public demo, legal docs (Impressum, privacy policy, ToS), and a product that serves a broad community. Expected approval timeline: 2 weeks to 6 months.

### Multi-Room Architecture (centralized only)

Only relevant if a centralized instance is pursued.

- New `rooms` and `room_members` tables. Most existing tables gain a `room_id` scope.
- `TrackedPlayer` stays global (LP fetched once per unique PUUID). Streak, price, and economy state are per-room.
- Room creator is admin. Joining requires an invite code. Economy parameters configurable per room.
- Scheduler: LP fetching is global, price/order/settlement logic becomes per-room.
- Poro, bank, playing income all become per-room-scoped.

**Open questions:** room lifecycle, member limits, admin disappearance, migration of existing single-tenant data, economy parameter bounds.

### Riot Sign-On (RSO)

Only available with a Production API key. Provides verified PUUID via OAuth2 instead of manual Riot ID entry. Benefits: proof of account ownership, immutable identity, no manual verification. Only worth implementing after Production key approval.

### Monetization (if centralized)

Riot's developer ToS allows charging for hosting/compute and premium features unrelated to Riot data. It prohibits charging for access to Riot data itself, real-money gambling, and selling Riot data.

Viable models for a centralized instance:
- **Hosting fee** ($3-5/month per market) - paying for server resources, not data.
- **Donations** (Patreon, GitHub Sponsors, Ko-fi) - simplest, covers small hosting costs.
- **Cosmetic premium** - custom themes, profile badges, extended history. Engineering effort probably not worth the revenue at realistic scale.

Realistic market: 50-500 active friend groups. This is a niche community tool, not a SaaS business. Optimize for sustainability, not growth.

### Market Sizing Reality Check

- LoL has ~150M monthly players. Fantasy esports exists (DraftKings, Fantasy LCS) but focuses on pro play.
- Zero direct competitors do "ranked LP stock market for friend groups."
- The niche is real but small: LoL friend groups who want a meta-game on top of ranked.
- Conversion from "plays LoL" to "would use a fantasy LP market" is low.
- The product's strength is personal and social - trading your friends' performance is fun because they're your friends. This doesn't scale to strangers.
- Global markets, federation, and multi-exchange designs don't serve the core use case and should not be pursued.

