# Productization Plan

This document is the canonical strategy reference for turning Nashordaq from a private friend-group project into a product.

It does not change the current implementation scope. It exists to answer two questions clearly:

1. What kind of product Nashordaq could become.
2. In what order that product should be built.

## Summary

Nashordaq should be productized as a **private League of Legends market game for friend groups**, not as a public trading network.

The recommended strategy is a dual-track approach with strict sequencing:

- **Track 1: self-hosted product first**
- **Track 2: hosted multi-room product second**

This sequence matches the current architecture, keeps early risk low, and creates a realistic path to validating demand before taking on the cost and policy burden of a hosted service.

## Why This Positioning Fits

### What the current repo already proves

The current application is already more than a prototype:

- It has a real loop: onboarding, trading, price updates, portfolios, leaderboards, and admin tools.
- It already supports repeat engagement rather than one-off novelty.
- It includes demo mode, simulation tooling, and broad backend test coverage.
- The economy is differentiated enough that it does not need more mechanics before testing product demand.

### What the current repo does not yet prove

The current codebase is still optimized for a trusted single-tenant environment:

- One deployment is one market.
- Authentication is still primarily oriented around an external proxy.
- Operations assume a private group and a technically capable operator.
- Several mechanics are fun for private play but create additional policy and distribution risk for a public hosted product.

## Market Research Summary

### Category reality

Nashordaq is not competing directly with broad League companion tools such as OP.GG, Blitz, Mobalytics, or Tracker Network. Those products focus on builds, stats, overlays, and improvement. Nashordaq's differentiator is a **social meta-game layered on top of ranked play**.

That means the likely buyer is not "a League player" in general. The likely buyer is:

- a friend group that already talks outside the game
- a Discord-based community with recurring social play
- a small streamer community that wants a private shared game

### Closest product patterns

The strongest product analog is not a stat tracker. It is a private-league fantasy platform pattern similar to Sleeper:

- group creation
- invite flows
- commissioner controls
- season resets
- social retention inside a private league

Nashordaq's market mechanics are novel, but the packaging should follow proven private-league behavior rather than open marketplace behavior.

### Demand assumption

The niche appears real but narrow:

- League has a massive player base, but only a small subset will want a social stock-market layer.
- The core appeal depends on personal familiarity: trading your friends is the joke and the hook.
- That social appeal weakens sharply in public or anonymous markets.

Conclusion:

- Optimize for retention of small private groups.
- Do not optimize for global discovery, public rooms, or scale-first growth.

## Product Thesis

### Recommended audience

Primary audience:

- 5-20 player friend groups
- Discord gaming groups
- streamer communities with light moderator structure

Secondary audience:

- self-hosters who want a polished private-side-game install
- community admins who want a hosted version later

### Core value proposition

"Create a private market around your friends' ranked climb."

The product should be sold on:

- social competition
- easy setup
- funny and memorable group dynamics
- recurring reasons to come back during the ranked season

It should not be sold on:

- serious finance simulation
- public player speculation
- esports analytics
- broad anonymous social networking

## Product Tracks

### Track 1: Self-Hosted Product First

This is the first product to build.

Definition:

- one deployment
- one private market
- one operator or small admin set
- Riot personal key usage
- simple setup path

Required product changes:

- built-in authentication as the default mode
- proxy auth retained as an advanced option
- cleaner onboarding and deployment docs
- feature flags for non-core mechanics
- stronger operator UX around setup and admin controls

Why this goes first:

- It is the closest step from the current architecture.
- It avoids immediate multi-room SaaS complexity.
- It is more compatible with the current single-process model.
- It creates real user validation before a hosted service exists.

Success criteria for Track 1:

- non-technical users can deploy it with minimal infrastructure knowledge
- friend groups can onboard without custom proxy/header setup
- groups continue using it for multiple ranked sessions

### Track 2: Hosted Multi-Room Product

This should only happen after Track 1 proves retention and hosted demand.

Definition:

- one managed service
- many private rooms
- invite-based access
- room-scoped economy state
- hosted billing and operations

Hosted product stance:

- rooms private by default
- no public market discovery at launch
- no dependency on risky mechanics for the core value proposition

Why this is second:

- hosted service requires room architecture, abuse controls, and support workflows
- hosted distribution introduces Riot policy and product-review constraints
- public hosting without proven retention would add complexity before learning

Success criteria before starting Track 2:

- external groups repeatedly ask for hosted convenience
- self-hosted adoption shows real multi-session retention
- the product can be described cleanly without depending on gambling-adjacent framing

## Product Shape For A Future Hosted Version

### Canonical product unit: the room

If Nashordaq becomes a hosted product, the core entity should be the **room**.

Expected new concepts:

- `Room`
- `RoomMember`
- `RoomInvite`
- `RoomSettings`
- `RoomSeason`

Expected data-model direction:

- Riot player identity remains globally deduplicated by PUUID.
- Economy state becomes room-scoped.
- Holdings, orders, leaderboards, bank state, poro state, and price history become room-scoped.

Expected behavioral defaults:

- a user may belong to multiple rooms
- each room has a commissioner/owner
- invite links are the main join path
- seasons and resets are room-level actions

### Product core vs optional mechanics

The hosted product should treat some features as core and some as optional.

Core product:

- account creation
- room creation and invites
- onboarding and Riot account linking
- trading
- leaderboard
- seasons and resets
- admin/operator controls
- analytics and retention tracking

Optional mechanics:

- `poro`
- rescue bank modifiers
- simulation utilities

Private/self-hosted-only mechanic:

- `gamba`

Default policy:

- self-hosted can keep optional mechanics available
- `gamba` remains private/self-hosted only and is excluded from the production-facing application
- hosted should launch with only policy-safe mechanics enabled
- hosted copy should avoid gambling-style positioning entirely

## Market Validation Plan

Demand should be validated at the group level, not the individual signup level.

### Who to recruit

- Discord communities that already queue ranked together
- small streamers with recurring viewer groups
- self-hosters interested in game-night tools
- GitHub users who explicitly ask for a hosted version

### What to measure

Primary metrics:

- room creation rate
- invite acceptance rate
- time from signup to first trade
- percentage of rooms still active after 7 days
- percentage of rooms still active after 30 days

Secondary metrics:

- average trades per active room
- percentage of users who return after their first session
- commissioner satisfaction
- number of groups asking for hosted convenience

### Validation threshold before hosted build-out

Use these thresholds as the minimum bar:

- at least 40% of activated rooms remain active after 30 days
- at least 50% of activated rooms complete a second real play session
- at least 5 external groups explicitly ask for hosted administration or managed hosting

If those thresholds are not met, keep Nashordaq self-hosted and niche.

## Monetization Strategy

### Recommended business goal

Treat Nashordaq as a sustainable niche product, not a startup-scale SaaS play.

### Monetization order

1. Open-source self-hosted product.
2. Free or low-cost hosted beta for design partners.
3. Paid hosted room subscriptions once retention is proven.

### Recommended pricing model

Charge for hosting and convenience, not Riot data.

Suggested hosted launch range:

- `$8-15/month` per room

Avoid:

- pay-to-win mechanics
- charging for access to Riot data itself
- ad-driven product design
- premium strategy features that distort the game balance

## Strategic Risks

### 1. Riot policy risk

Some current mechanics increase risk for a public hosted product, especially anything that reads as gambling or betting.

Mitigation:

- keep risky mechanics behind feature flags
- make the core product viable without them
- ensure hosted positioning remains private-league and social, not gambling-oriented

### 2. Product-market-fit risk

The niche may be too small for a meaningful hosted business.

Mitigation:

- validate with self-hosted adoption first
- focus on room retention, not traffic
- optimize for sustainability rather than growth narratives

### 3. Architecture risk

The current single-tenant architecture does not become multi-room cheaply.

Mitigation:

- do not rush hosted
- add room scoping only after demand is proven
- keep the room model explicit rather than bolting it on implicitly

### 4. Scope risk

It is easy to spend time on side mechanics rather than product foundations.

Mitigation:

- prioritize auth, rooms, invites, seasons, and admin controls
- treat `poro` and similar features as optional
- keep `gamba` out of the production-facing product entirely
- measure whether they improve retention before elevating them into the product core

## Recommended Execution Order

### Phase 1: Productize the current private deployment

- add built-in auth
- reduce infrastructure friction
- tighten setup and onboarding
- improve operator-facing docs
- keep single-tenant architecture

### Phase 2: Validate real-world retention

- onboard external test groups
- track room-level activation and retention
- collect commissioner feedback
- verify whether groups ask for hosted convenience

### Phase 3: Prepare hosted architecture

- introduce room-scoped models and APIs
- add invites, seasons, and room settings
- add audit logging, analytics, and abuse controls
- keep hosted launch scope limited to private rooms

### Phase 4: Launch hosted beta

- start with a small number of curated groups
- disable risky mechanics by default
- prove operational support and room retention
- only then standardize pricing and public availability

## Research Inputs

The research that informed this plan is based on the current repo plus the following external references reviewed on **2026-04-04**:

- Riot Developer Portal: <https://developer.riotgames.com/docs/portal>
- Riot General Policies: <https://developer.riotgames.com/policies/general>
- Riot FAQ / production-key context: <https://developer.riotgames.com/docs/faqs>
- Riot League of Legends docs: <https://developer.riotgames.com/docs/lol>
- Sleeper private-league support docs: <https://support.sleeper.com/en/>
- Blitz League of Legends product surface: <https://blitz.gg/lol>
- OP.GG desktop/app surface: <https://op.gg/desktop/en>
- Tracker Network LoL app launch context: <https://tracker.gg/bfv/articles/lol-overwolf-app-launch>
- Fantasy sports market sizing context: <https://www.grandviewresearch.com/industry-analysis/fantasy-sports-market-report>

## Defaults And Assumptions

- This plan assumes Nashordaq remains a web product first.
- This plan assumes English-first documentation and UI for the first productized version.
- This plan assumes the strongest retained use case is private social play, not open discovery.
- This plan assumes self-hosted and hosted products should share a codebase where practical, but not a launch timeline.
- This plan does not commit the project to building a hosted product. It defines the order and conditions under which that would make sense.
