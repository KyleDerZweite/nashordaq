# Product Requirements Document

## Objective

Create a private, web-based platform where users can speculate on the ranked progression of a defined list of League of Legends accounts.

## Target Audience

A closed, trusted friend group. Public registration and email verification are out of scope.

## Core User Flows

1. **Authentication:** User access is gated by an external Identity-Aware Proxy (e.g., Zitadel/Pangolin). Upon successful proxy authentication, the user is seamlessly passed to the Nashordaq interface. The backend automatically provisions a starting balance of 10,000 virtual currency the first time it detects a new `Remote-User` header.

2. **Market Overview:** Users can view a dashboard listing all tracked LoL accounts with their current share price and last update time.

3. **Trading:** Users can place buy or sell market orders for whole shares of tracked players. Orders are saved as PENDING and executed at the next price update (forward pricing). Users can cancel pending orders before execution.

4. **Portfolio Management:** Users can view their cash balance, owned shares with current market values, and total net worth.

5. **Leaderboard:** Users can view a ranked list of all participants ordered by total net worth (cash + holdings value).

## Constraints

- **Long only:** Users cannot short sell. Selling requires owning sufficient shares (accounting for pending sell orders).
- **Whole shares only:** Fractional share quantities are not supported.
- **Market orders only:** No limit orders or other order types.
- **Pre-seeded players:** The list of tracked players is defined in a configuration file (`players.json`) and loaded at startup. There is no runtime API to add or remove players.

## System Requirements

1. **Riot API Integration:** The system fetches Solo Queue rank and LP data for all tracked accounts at a configurable interval (default: 30 minutes).

2. **Pricing Engine:** Share prices are computed from Absolute LP using a formula that incorporates base volatility, momentum streaks, per-player obfuscation, and random noise. See [Economy Mechanics](ECONOMY_MECHANICS.md) for details.

3. **Forward Pricing:** Orders execute at the price calculated during the next scheduler cycle, not at the price visible when the order was placed. This prevents front-running based on live match viewing.

4. **Transaction Ledger:** Every executed order produces an immutable transaction record. Balances and holdings are updated atomically within the same database transaction as price updates.
