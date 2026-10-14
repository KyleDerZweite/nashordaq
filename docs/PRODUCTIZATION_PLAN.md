# Productization plan

Nashordaq's accepted product is a self-hosted private market for a League of Legends friend group. [ADR-0001](adr/0001-self-host-baseline.md) owns the standalone decision, and [PRD](PRD.md) owns current product behavior. This strategy document does not authorize new features or change those contracts.

## Current baseline

One deployment has one market and exactly one administrator. Local account access, invitations, password recovery, isolated demo sessions, permanent streamer aliases and member-visible game interventions are implemented. Docker Compose and Podman Compose build local images. Operator commands provide live backup, fresh restore and supported-schema update preflight.

The baseline is merged and installed through a git clone of `main`, supplied environment configuration and Compose. Updates and recovery use exact commits and matching backups. [Self-host acceptance](SELF_HOST_ACCEPTANCE.md) records technical evidence separately from live Riot verification and owner acceptance.

Local account access works without Riot. Live play requires a valid operator-owned key. Gamba remains an explicit private-use option, disabled by default. A future production-facing application would exclude Gamba and require its own policy review. This document claims no approval or compliance with current Riot policies.

## Validate private-group use

The product's appeal depends on participants knowing the people whose ranked performance they trade. Candidate audiences remain small friend groups, Discord gaming groups, self-hosters and streamer communities. These are audience hypotheses, not measured adoption.

An external group should be able to install the application with basic Linux and container knowledge, invite members, link their own Riot accounts and complete a first trade. Operator feedback should cover setup, recovery, backup and maintenance. Product feedback should cover whether the group returns for later ranked sessions.

The suggested measurements are invitation acceptance, time to first trade, return for a second play session, seven-day and thirty-day group retention, and operator satisfaction. No retention data or validated market size is recorded here. Collect evidence before selecting more economy mechanics or infrastructure.

## Future hosted service

Hosted multi-room operation, monetization, Riot Sign-On and OAuth/OIDC remain exploratory. They are outside the current baseline and active implementation contract. They need a new accepted design before implementation; the standalone code does not contain a prebuilt authentication-provider framework.

A possible hosted service would need explicit room ownership and room-scoped economy state. Candidate concepts include `Room`, `RoomMember`, `RoomInvite`, `RoomSettings` and `RoomSeason`. Riot identity might be shared while balances, holdings, orders, history, bank state and leaderboards belong to individual rooms. These are proposals, not current domain vocabulary or component responsibilities.

The historical strategy proposed private rooms, invitation access, seasons, operator controls and limited initial distribution. Optional Poro, rescue-bank modifiers and simulation tooling would need separate product decisions. Gamba would remain excluded from that production-facing path. Hosted operation would also need support, abuse controls, policy review and verified operations.

Before revisiting hosted work, the historical plan proposed at least 40% of activated groups returning after thirty days, at least 50% completing a second play session, and at least five external groups asking for managed hosting. These are proposed research thresholds. They are neither measured results nor requirements for this baseline.

## Exploratory monetization

The historical strategy considered charging for hosting and convenience, with a possible range of $8 to $15 per private room each month. That price has not been validated and is not a current offer. Billing, room subscriptions and a hosted beta remain unselected ideas.

Any future commercial plan would need current primary-source policy research and an explicit owner decision. The project should preserve fair game rules rather than sell advantages through premium mechanics.

## Historical research context

The previous strategy notes were assembled on 2026-04-04. They compared the product with private-league fantasy platforms and League companion tools. Those comparisons support questions to investigate, not claims of current demand, competitive coverage or legal permission.

The original primary references included the [Riot Developer Portal](https://developer.riotgames.com/docs/portal), [Riot General Policies](https://developer.riotgames.com/policies/general), [Riot FAQ](https://developer.riotgames.com/docs/faqs), [League API documentation](https://developer.riotgames.com/docs/lol), [Sleeper support](https://support.sleeper.com/en/), [Blitz](https://blitz.gg/lol) and [OP.GG](https://op.gg/desktop/en). Recheck current sources if a future distribution or policy decision depends on them.
