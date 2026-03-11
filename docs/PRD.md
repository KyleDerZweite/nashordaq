# Product Requirements Document

## Objective

Create a private, web-based platform where users can speculate on the ranked progression of a defined list of League of Legends accounts.

## Target Audience

A closed, trusted friend group. Public registration and email verification are out of scope.

## Core User Flows

1. **Authentication:** User access is gated by an external Identity-Aware Proxy (e.g., Zitadel/Pangolin). Upon successful proxy authentication, the user is seamlessly passed to the Nashordaq interface. The backend automatically provisions a configured starting balance the first time it detects a new `Remote-User` header.

2. **Market Overview:** Users can view a dashboard listing all tracked LoL accounts with their current share price and last update time.

3. **Trading:** Users can place buy or sell market orders for whole shares of tracked players. Orders execute immediately at the currently visible market price. Sell proceeds are adjusted by holding time (short-hold reduction and long-hold bonus). Executed buy orders can be reverted for full refund within a short grace period (configurable, default 60 seconds), as long as none of those shares were sold.

4. **Portfolio Management:** Users can view their cash balance, owned shares with current market values, active Gamba exposure, outstanding bank debt, and total net worth.

5. **Leaderboard:** Users can view a ranked list of all participants ordered by total net worth (cash + holdings value + active Gamba mark value - outstanding bank debt).

6. **Bank Credit:** Clicking the balance card opens a bank modal where onboarded player accounts can borrow virtual currency. Borrowing increases cash immediately, the first interest charge is added immediately, outstanding debt then compounds by 2.5% every 120 hours, and repayment is allowed at any time.

7. **Playing Income:** Onboarded player accounts earn a small direct cash reward when the system detects that their linked Riot account completed a new Ranked Solo 5v5 match. Rewards are credited once per completed match, use the player's current share price as the base, and ignore remakes/short games.

## Constraints

- **Long only:** Users cannot short sell. Selling requires owning sufficient shares (accounting for pending sell orders).
- **Whole shares only:** Fractional share quantities are not supported.
- **Market orders only:** No limit orders or other order types.
- **Self-onboarding players:** Each user links their own Riot account on first access by submitting `game_name`, `tag_line`, and `display_name`. Linked players become tracked in the market. Deletion is out of scope.

## System Requirements

1. **Riot API Integration:** The system fetches Solo Queue rank and LP data for all tracked accounts at a configurable interval (default: 30 minutes).

2. **Pricing Engine:** Share prices are computed from Absolute LP using a formula that incorporates base volatility, momentum streaks, per-player obfuscation, and random noise. See [Economy Mechanics](ECONOMY_MECHANICS.md) for details.

3. **Immediate Execution + Hold Adjustment:** Orders execute at the visible market price at submission time. Sell proceeds are adjusted by holding duration to discourage rapid flips and reward longer holds.

4. **Transaction Ledger:** Every executed order produces an immutable transaction record. Balances and holdings are updated atomically within the same database transaction as price updates.

5. **Bank Debt Ledger:** Borrowing, interest capitalization, and repayments are stored as immutable bank-ledger entries. Outstanding debt is account-level and is not represented as a trade order.
