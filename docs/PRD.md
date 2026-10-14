# Product requirements

## Objective

Create a private, web-based platform where users can virtually invest in the ranked progression of a defined list of League of Legends accounts.

## Target audience

A closed, trusted friend group. Public registration and email verification are out of scope.

## Accepted self-host baseline

[ADR-0001](adr/0001-self-host-baseline.md) defines the accepted requirements for [issue #16](https://github.com/KyleDerZweite/nashordaq/issues/16) and [issue #17](https://github.com/KyleDerZweite/nashordaq/issues/17). Local invite-based access replaces proxy authentication. One administrator may also participate in the market. Game-changing administrative actions are visible to members. Demo access and Streamer Mode follow the same decision.

Public registration, a mail-server requirement, OAuth/OIDC, additional administrators and hosted multi-room operation are outside this baseline. A fresh installation starts with empty data. Supported updates preserve complete standalone schema version 1 between compatible commits; recovery uses the old commit and its matching backup.

Local setup, invitation registration, password recovery, sessions, isolated demo sessions, stable identity presentation, administrator participation and member-visible game interventions are implemented. Compose packaging and operator backup, restore and update preflight are implemented. The baseline is merged and installable through a git clone of `main`, supplied environment configuration and Compose. [Self-host acceptance](SELF_HOST_ACCEPTANCE.md) separates commit-specific technical verification, live integration evidence and owner acceptance.

## Current core user flows

1. **Authentication:** The operator creates the sole administrator through the one-time setup link in the application log. The administrator issues single-use invitation links valid for seven days and can revoke unused links. Invited members choose their own username and password without email or Riot details. Users sign in with local username/password credentials. Sessions last seven days and logout immediately revokes the current session. Users change their password after verifying their current credential. The administrator issues revocable one-hour reset links, and the operator can recover the existing sole administrator on the server. Successful password replacement ends every affected session. Setup and login work without a Riot key. All game information requires login. See [Architecture](ARCHITECTURE.md#authentication-and-session-trust-boundary) for the security boundary.

2. **Market Overview:** Users can view a dashboard listing all tracked LoL accounts with their current share price and last update time.

3. **Trading:** Users can place buy or sell market orders for whole shares of tracked players. Orders execute immediately at the currently visible market price. Shares are locked for a minimum holding period (default 4 hours) after purchase before they can be sold. Executed buy orders can be reverted for full refund within a short grace period (configurable, default 120 seconds), as long as none of those shares were sold.

4. **Portfolio Management:** Users can view their cash balance, owned shares with current market values, outstanding bank debt, total net worth, and any optional private-only side-position exposure when that feature is enabled in a private deployment.

5. **Leaderboard:** Users can view a ranked list of all participants ordered by total net worth (cash + holdings value + optional side-position mark value - outstanding bank debt).

6. **Bank Failsafe:** Clicking the balance card opens a bank modal where onboarded player accounts can claim a fixed rescue loan only after falling under the configured debt-adjusted net-worth threshold. The rescue adds cash immediately, adds an immediate opening interest charge, rolls forward every 120 hours at a low fixed rate, can be repaid at any time, and is single-use until an admin restores access.

7. **Playing income:** Onboarded player accounts earn a small direct cash reward when the system detects that their linked Riot account completed a new Ranked Solo 5v5 match. Rewards are credited once per completed match, use the player's current share price as the base, and ignore remakes/short games.

## Constraints

- **Long only:** Users cannot short sell. Selling requires owning sufficient shares (accounting for pending sell orders).
- **Whole shares only:** Fractional share quantities are not supported.
- **Market orders only:** No limit orders or other order types.
- **Self-onboarding players:** Each user, including the administrator, can link their own Riot account by submitting `game_name` and `tag_line`. Linked players become tracked in the market. Deletion is out of scope.
- **Production-compliant product path:** Any future Riot-compliant production application excludes the private-only `gamba` mechanic entirely and frames Nashordaq as a virtual investing and social market product.

## System requirements

1. **Riot API Integration:** The system fetches Solo Queue rank and LP data for all tracked accounts at a dynamic interval derived from tracked-player count and the configured request budget. The scheduler checks whether a refresh is due every 30 seconds. See [Architecture](ARCHITECTURE.md#scheduler-pipeline).

2. **Pricing Engine:** Share prices are computed from Absolute LP using a formula that incorporates base volatility, momentum streaks, per-player obfuscation, and random noise. See [Economy Mechanics](ECONOMY_MECHANICS.md) for details.

3. **Immediate Execution + Market Impact:** Orders execute at the visible market price at submission time. Buys and sells apply market impact based on order size, and bought shares remain locked during the minimum holding period.

4. **Transaction Ledger:** Every executed order produces an immutable transaction record. Balances and holdings are updated atomically within the same database transaction as price updates.

5. **Bank Debt Ledger:** Borrowing, interest capitalization, and repayments are stored as immutable bank-ledger entries. Outstanding debt is account-level and is not represented as a trade order.

Administrator and participant views are available through the account menu. Onboarded administrators use ordinary trading, portfolio, bank and profile actions under the same economy rules. Linking can be dismissed, preserving account administration when Riot is unavailable. The game activity list shows successful rescue-access restorations with actor, affected member, time and the change in remaining uses. Failed interventions and account access operations do not create activity entries.

## Identity and demo behavior

Normal views show the local username and linked RiotName. Streamer Mode uses each participant's permanent League alias across all views and reloads. It hides personal names, Riot tags and identifying links. Editing a Riot profile requires explicitly leaving Streamer Mode. The feature protects rendered presentation; it does not hide legitimate identity data from authenticated API consumers.

Explicit demo mode automatically loads a shared simulated market and requires `demo/demo` login. Every browser session has separate temporary balance, holdings and orders without administrator permissions. Reload preserves a valid session. Logout immediately deletes personal state. Thirty minutes of inactivity ends access, and the minute-based cleanup removes abandoned state while preserving shared market data. Trusted user interaction renews activity; polling and streams do not. Browser closure is not an immediate deletion signal.

Gamba is disabled by default. Operators can enable the existing mechanic explicitly for private use; this baseline adds no economy mechanics. [Economy mechanics](ECONOMY_MECHANICS.md) owns formulas and configurable defaults.
