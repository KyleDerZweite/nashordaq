---
status: accepted
---

# Standalone authentication for the self-host baseline

Nashordaq must be installable by an external operator with a Linux server and basic container knowledge. One installation runs one private market for one group. Local accounts in the existing SQLite database become the standard, removing the need for an external authentication service. Both Docker Compose and Podman Compose are supported.

This decision replaces the requirement for external proxy authentication. Proxy authentication is removed from the target contract. OAuth and native OIDC remain future options outside this baseline. Local users register through time-limited administrator invitations. Open registration and a required mail server are excluded.

The deployment flow is `git clone`, `cp .env.example .env`, environment configuration and `podman-compose up -d`, with an equivalent Docker Compose flow. Images build locally from a specified release tag. Published application images are not a prerequisite. Gamba is disabled by default and can be enabled explicitly for private installations.

The first registered local user becomes the administrator. On first startup, the application generates a one-time setup link in the container log. Only that link permits initial administrator registration. Subsequent registration requires an invitation. The administrator may trade after normal Riot onboarding. Only administrative interventions in the game, such as restoring rescue-loan access, appear in an activity log visible to authenticated members.

Local users log in with a username and password. Email is not required. Normal views show username and linked RiotName. Streamer Mode replaces personal names with League of Legends character names. An additional custom display name is outside the current contract.

Compose publishes a configurable HTTP port for LAN access or an existing reverse proxy. The operator's reverse proxy terminates public HTTPS. Pangolin and Newt are not deployment requirements. SQLite data resides in a host-directory bind mount outside the container. Game information requires an authenticated session.

The baseline has exactly one administrator and no management of additional administrator roles. The administrator creates single-use password-reset links valid for one hour. A CLI recovery command with access to SQLite restores an inaccessible administrator account. Invitations are single-use and valid for seven days. Unused invitation and reset links can be revoked. Local login sessions last seven days; logout ends the current session immediately. Password changes and resets end all sessions belonging to that user.

Transitioning from the previous proxy installation starts with a fresh database and discards its previous data. Existing proxy accounts and game state are not migrated. Import remains a future option. The tested update contract begins between the new standalone releases. This transition decision does not authorize immediate deletion of an existing database.

Operational acceptance covers fresh installation under Docker Compose and Podman Compose, persistence after restart, consistent live backup, restore and an update from the previous supported release. Recovery after a failed update uses the old release and a matching backup.

Demo deployment is selected explicitly through environment configuration and loads demo data automatically. The shared login is `demo/demo`. Each browser session receives a separate temporary demo user with its own balance, portfolio and orders. Visitors share a simulated market. Logout immediately deletes personal game state. Without logout, a session expires after thirty minutes of inactivity and its data is cleaned up automatically. Reload preserves the session. Cleanup preserves the shared demo market.

Each user receives a permanent champion-based streamer alias. The same alias appears across all views, including the leaderboard and activity log. Username, RiotName, Riot tag and identifying links are hidden in Streamer Mode. Item and ability names may extend the alias pool if champion names are exhausted.

A missing or invalid Riot key does not prevent local login or administration. The UI displays the configuration error. New Riot links and market updates require a valid key; failed updates do not change prices. Operators replace the key in the environment configuration and restart the containers. Demo mode requires no Riot key.

The overall contract was approved on 2026-10-13. Repository rules and canonical documents refer to this target contract. The implementation remains proxy-based until code and tests are changed. This ADR records accepted requirements, not delivered functionality.

A hosted service remains a future option. Multi-room operation is outside this baseline. [PRODUCTIZATION_PLAN.md](../PRODUCTIZATION_PLAN.md) remains the strategy reference for that future direction.

This contract supersedes the old built-in authentication proposal in [ROADMAP.md](../ROADMAP.md). Automatic mode detection and proxy-header precedence disappear with proxy authentication. Riot onboarding remains separate from local account access.

The published requirements and testing contract are recorded in [spec issue #19](https://github.com/KyleDerZweite/nashordaq/issues/19).
