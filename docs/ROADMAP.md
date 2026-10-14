# Roadmap

The current product is one self-hosted private market per group. [PRD](PRD.md) owns behavior, [ADR-0001](adr/0001-self-host-baseline.md) owns the standalone decision, and [self-host acceptance](SELF_HOST_ACCEPTANCE.md) owns implementation evidence and remaining checks.

## Implemented standalone baseline

[Spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19) and slices #20 through #30 implement local username/password authentication, one-time administrator setup, member invitations, password recovery, revocable sessions and the private game-data gate. Proxy identity and automatic anonymous demo fallback are removed. OAuth/OIDC is outside the baseline.

The sole administrator can trade after normal Riot onboarding. Successful game interventions produce an atomic activity record visible to authenticated members. Normal views show username and linked RiotName. Streamer Mode uses permanent aliases and hides personal names, tags and identifying links.

Explicit demo deployment requires `demo/demo` login and gives each browser session separate temporary state in a shared simulated market. Logout deletes personal state immediately; thirty minutes of inactivity ends access, and automatic cleanup preserves shared market data.

Docker Compose and Podman Compose build locally from pinned inputs and retain SQLite in a host bind directory. Gamba is disabled by default. Operator commands provide administrator recovery, consistent live backup, fresh restore and supported-schema preflight. The initial complete schema is version 1; partial development schemas and old proxy data are unsupported.

The implementation is unreleased. Final acceptance must distinguish current-revision checks, live Riot, operator public HTTPS, release-tag installation and owner judgment. The first standalone release has no released predecessor. The following release must verify its advertised predecessor update and matching-backup recovery.

## Existing economy

The completed economy includes per-match LP attribution, match-driven pricing, inactivity pressure, FIFO holding locks, buy reverts, trade impact, loss-side streak amplification, low-price loss dampening, playing income, bank rescue loans and optional duration-based Gamba settlement. [Economy mechanics](ECONOMY_MECHANICS.md) remains the canonical source for formulas and defaults. The standalone baseline changes none of them.

The former proxy-email identity direction is superseded by local usernames and sessions. Its identity headers and role matching are not supported runtime configuration.

## Unselected work

Limited share supply and player-to-player trading remain possible ideas. They would need decisions on supply, positions, pricing and the order interface before implementation. Current trading remains whole-share market orders under the existing economy rules.

Poro automation resistance remains an open product concern. The previous coordinate-validation idea is a proposal, and browser-supplied coordinates alone would not prove human input. No Poro redesign belongs to the standalone baseline.

Additional queues, including Ranked Flex, TFT Ranked and TFT Double Up, are possible later slices. Their separate APIs, rank handling and product contracts need review before implementation.

Hosted multi-room operation, Riot Sign-On, OAuth/OIDC, seasons and monetization remain exploratory. [Productization plan](PRODUCTIZATION_PLAN.md) records those ideas and research assumptions. They are not current delivery goals or implicit architecture requirements.
