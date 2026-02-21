# Product Requirements Document

## Objective
Create a private, web-based platform where users can speculate on the ranked progression of a defined list of League of Legends accounts.

## Target Audience
A closed, trusted friend group. Public registration and email verification are out of scope.

## Core User Flows

**Core User Flows**
1. **Authentication:** * User access is gated by an external Identity-Aware Proxy. 
    * Upon successful proxy authentication, the user is seamlessly passed to the Nashordaq interface.
    * The backend automatically provisions a starting balance (e.g., 1000 currency) in the database the first time it detects a new `X-Remote-User` header.
2. **Market Overview:** Users can view a dashboard listing all tracked LoL accounts, their current rank, current LP, and current share price.
3. **Trading:** Users can buy or sell shares of tracked players at the current market price.
4. **Portfolio Management:** Users can view their liquid currency, owned shares, and total net worth.
5. **Leaderboard:** Users can view a ranked list of all participants based on total net worth.

## System Requirements

1. **Riot API Integration:** The system must fetch rank and LP data for tracked accounts at a regular interval (e.g., 30 to 60 minutes).
2. **Pricing Engine:** The system must calculate and update the share price of each tracked account based on a mathematical formula tied to their LP/tier changes.
3. **Transaction Ledger:** The system must record all buy and sell orders to ensure accurate balances and prevent race conditions.
