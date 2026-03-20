# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-03-20

### Added

- **Per-match pricing engine** - every ranked match is individually detected, attributed its LP delta, and priced sequentially. A 3-game session now produces three distinct price movements instead of one averaged move.
- **Gamba (leveraged positions)** - place leveraged bets on a randomly selected player. Lock in a cash amount, hold for 24-168 hours, and settle at a 2.0x-4.0x multiplier based on hold duration. Can be toggled on/off via `NASHORDAQ_GAMBA_ENABLED`.
- **Playing income** - linked players earn passive credits when their Riot account completes ranked matches. Wins pay more than losses. First 3 games per day pay full rate, subsequent games at 65%.
- **Bank & rescue loans** - when debt-adjusted net worth drops below 250, claim a one-time 750-credit rescue loan. 2% flat interest charged every 120 hours.
- **Market impact (slippage)** - orders now move the market price. Impact scales with order size relative to configurable liquidity depth.
- **Minimum holding period** - shares must be held for a configurable duration before they can be sold. Prevents instant flip arbitrage.
- **Streamer mode** - toggle name obfuscation across the entire UI for streaming or screenshots.

### Changed

- **Full economy reset** - all balances restored to 1000 + retroactive playing income. All trading history cleared. Prices replayed from match data through the new pricing formulas.
