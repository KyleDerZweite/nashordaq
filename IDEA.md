# Multi-Room Public Access — Design Ideas

Status: **Thinking / Not yet decided**

## Goal

Make Nashordaq usable by multiple friend groups without requiring everyone to be behind the Pangolin IAP. The app becomes a public website with isolated "rooms" that each function as an independent market.

## Two-Tier User Model

### IAP Users (Pangolin-authenticated)
- Identified by `Remote-User` header as today.
- Can create new rooms.
- Can also join rooms like anyone else.

### Guests
- Visit the public site, see rooms (or follow a direct link).
- Join an existing room by entering a room code.
- Create a profile (display name, optionally link LoL account) on join.
- Cannot create rooms.

## Room Concepts

- Each room is an independent market with its own tracked players, orders, holdings, leaderboard.
- Room creator is the admin.
- Room has a **join code** (e.g., `NASH-7K2F`) set by the admin.
- Room has a **player mode** setting:
  - **Self-link:** Each member links their own LoL account (current onboarding behavior, per room).
  - **Admin-curated:** Room admin adds the tracked LoL profiles; members just trade.

## Guest Identity Persistence (Unsolved — Options Below)

The core problem: when a guest returns later, how do they prove they're the same person?

### Option 1: Device Token (simplest, recommended for now)
- On profile creation, the app issues a random bearer token stored in `localStorage`.
- All subsequent requests use that token.
- If the guest loses it (cleared storage, new device), the room admin generates a one-time recovery link.
- Pros: zero auth stack, no passwords, no login forms.
- Cons: tied to one browser; clearing storage = locked out until admin helps.

### Option 2: Username + Self-Set Passphrase
- Guest picks a display name and passphrase when creating their room profile.
- To return, they enter both.
- Pros: works across devices.
- Cons: requires password hashing (bcrypt/argon2); people forget passphrases.

### Option 3: Recovery Code
- On profile creation, the app generates a random code (e.g., `NASH-4K7F-XP2M`), shown once.
- To re-login from a new device, enter display name + recovery code.
- Pros: no user-chosen passwords.
- Cons: people lose the code (same admin-reset fallback as Option 1).

### Future: External Auth Providers
- Matrix server as an auth provider, or other OAuth/OIDC providers.
- Separate concern from the room model — can be layered on later.

## Data Model Changes (Rough Sketch)

New tables:
```
rooms
  id, name, code_hash, player_mode (self_link | admin_curated),
  created_by (user_id), created_at

room_members
  id, room_id, user_id, role (admin | member), display_name, joined_at
```

Existing tables gain `room_id`:
- `tracked_players` — scoped to a room
- `holdings` / `holding_lots` — scoped to a room
- `orders` / `transactions` — scoped to a room
- `price_history` — scoped to a room (via player)
- `leaderboard` — computed per room

User table changes:
- `users` unifies IAP users and guests.
- IAP users have `username` (from header).
- Guests have a hashed bearer token.
- Both can be members of multiple rooms.

## Scheduler Impact

- Currently one job fetches LP for all tracked players.
- With rooms: still one global job (tracked players across all rooms), but price updates and order execution are per-room.
- Alternatively, deduplicate: if two rooms track the same player (same puuid), fetch LP once but compute prices independently per room (since gamma/streak are per-room).

## Open Questions

- Should rooms be listed publicly, or only joinable via direct link?
- Should there be a room member limit?
- Can a guest be in multiple rooms?
- What happens when a room admin disappears? (Transfer ownership? Auto-expire?)
- How to handle the Riot API rate limit if many rooms track many players?

## Additional Game Scoring Ideas

- Add recent KDA from the last matches into the score calculation so price movement can reflect not only ranked LP changes but also short-term in-game performance.
