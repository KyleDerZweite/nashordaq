# Standalone self-host acceptance

This record traces all 52 stories in [spec #19](https://github.com/KyleDerZweite/nashordaq/issues/19) for [slice #30](https://github.com/KyleDerZweite/nashordaq/issues/30). The standalone implementation is unreleased. Technical verification does not establish owner acceptance or authorize release publication, deployment or deletion of operator data.

Recorded on 2026-10-14 against integration `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`, after slices #20 through #29. Documentation-only changes follow that revision. Earlier runtime scenarios below identify their actual deployed source. Current-head runtime evidence is recorded as F, N and E below. Independent review, final fixes, final check refresh and GitHub CI remain pending. A prior passing scenario is not automatically a current-head result.

## Status and ownership

PASS means the named scenario passed at its recorded revision and provider. UNEXECUTED means the scenario has no qualifying evidence. A current refresh marked pending is UNEXECUTED at the current revision. PASS for a narrow refresh establishes only its named behavior, not a complete replay of earlier journeys. FAILED means an observed check failed; a later correction must identify its new evidence. Owner acceptance is pending for the complete product, including technically passing scenarios.

The integration owner owns current-head checks, review and evidence refresh. The release owner owns an eventual standalone tag, its fresh installation and the next release's actual predecessor update. The deployment operator owns public DNS, a trusted certificate and reverse-proxy acceptance. The Riot operator owns an authorized valid key and live linking, refresh and key-replacement checks. No Riot key was requested or used for the normal no-key local installation.

## Recorded technical evidence

These summaries retain the scenario, provider, revision and result in the repository. Private credentials, session values and usable setup, invitation or reset URLs are deliberately excluded. Supplemental implementation logs and screenshots are temporary engineering records; they are not the only evidence for the outcomes below.

| ID | Revision and provider | Recorded result |
|---|---|---|
| T | Source `7553907cdb5fc8364a5990b1aee37796fc54212d`, exact tree equal to integration `a9807dc`; host Python 3.14.7, SQLite 3.50.2 | PASS. `uv run pytest -v` completed with 286 passed and one optional live Riot skip in 308.28 seconds. Ruff check and format passed, 59 files unchanged. Test configuration used a synthetic key, with no live request. Earlier frontend lint, format and build passed; final combined frontend checks and CI need refresh. |
| P | Source `5c11719638220639f4f87351bb66da3ae2dca156` and earlier #27 verification checkpoints; Podman 5.8.4, podman-compose 1.5.0 | PASS. Local image builds, frontend-only HTTP, both health checks, host directory bind, empty-key setup, invitations and restart persistence. A backend IP change initially broke Nginx routing; dynamic DNS resolution fixed it. The rerun changed the address again and retained healthy HTTP, session, administrator identity, balance and closed setup. Default Gamba returned 404 with hidden UI; explicit private opt-in worked. LAN-address access ran from the host, not a second physical LAN client. |
| A | `69fcbade1ee96cd1c8224e84a6457b54d0095571`; actual Podman and Docker Engine 29.9.0, Compose 5.6.0 | PASS. Existing accounts and completed setup survived full-stack recreation with an empty key. Browser password change rejected the wrong credential, accepted the correct credential, ended an independent session and required the new password. Admin-issued reset consumed once, cleared its URL token and ended member sessions. Podman terminal recovery hid both password prompts. Docker protected-stdin recovery retained the same sole administrator and game state while revoking the old session. |
| I | `abbd7010f257c25af2337cb7909c12c1e01bcda7`; actual Docker Engine 29.9.0, Compose 5.6.0, browser and controlled external HTTP Riot fixture | PASS with substitute upstream. The real Riot adapter linked administrator and member. Each bought the other's stock through the rendered form and received separate holdings. A spent-rescue fixture allowed a real administrator restoration; the member saw actor, affected member, UTC time and zero-to-one change. Streamer Mode hid recognizable names, tags and links across rendered market, account, holdings, leaderboard, orders and activity at 390 pixels without page overflow. A 503 fixture rejected profile changes and scheduled refresh without changing stored identity, prices or history. Restoring the fixture allowed the same form to retry while retaining alias and balance. This is not live Riot evidence. |
| S | `1fc1438e2ceacc24cf8b527dc682534e390482c9`; real FastAPI/Vite/SQLite browser, no key, disposable private Gamba opt-in | PASS. At 390 and 1280 pixels, normal identities were visible before Streamer Mode hid names, tags, identifying links, accessible labels and editor values. Aliases matched across player details, trades, portfolio, orders, leaderboard, activity, administrator inspections, reset controls, simulation and Gamba. Reload and backend restart retained aliases. Profile editing required explicitly turning Streamer Mode off. This provider was local development, not Compose. |
| D | `a949a97ba4f3c54c2648698fc1e4568ac4a414f7`; Podman Compose, two independent browser profiles, explicit demo, no key | PASS. Each `demo/demo` login created a separate user with balance 1000 and the same 12 seeded players. One visitor bought a share; the other retained its balance and empty portfolio/orders. Guessed cross-visitor order and portfolio routes returned 404. Reload retained the first user's identity and state. Logout physically removed personal rows. The untouched second visitor expired after actual thirty-minute inactivity; scheduled cleanup removed its user/session and personal rows before a probe, returned the browser to login, and retained 12 players and 362 history rows. Background observations did not renew its deadline. This is elapsed-time evidence, separate from controlled-time tests. |
| B | `896a5148be8bbecd73140e09b6e2d1b134f77c5f`; actual Docker Engine 29.9.0, Compose 5.6.0, SQLite WAL and browser | PASS. A held read boundary left a committed 64 MiB fixture table visible only through WAL. During CLI online backup, real HTTP buy/revert requests continued, including 75 writes during the snapshot. The 67,506,176-byte snapshot passed integrity checks and included the table and coherent account/game state. Protected export was byte-identical. Exact matching source restored into a separate fresh stopped installation. Browser administrator/member sessions resumed with snapshot balances, holdings, aliases and one activity event, rather than later source writes. Setup stayed closed and existing-password login passed. The backup digest remained unchanged. |
| U | Candidate application `053765a2ebc64dafae7b635191ccbef7f6e5a6e9`, final source `7553907`, old source `896a514`; actual Podman, pinned Python 3.12.13, SQLite 3.40.1 | PASS for development-artifact compatibility only. Image source hashes matched all 30 application Python files. Complete version 1 preflight and startup retained accounts, administrator identity, sessions, closed setup, balances, holdings, orders, history, aliases and access-token lifecycle. A synthetic future version 999 failed preflight and startup without changing the database or matching snapshot. Exact old code restored its pre-update backup into a separate fresh installation and recovered the same account/game state and password logins. These are not released predecessor artifacts. |
| H | Deployed `896a514`; actual Podman images and temporary local self-signed reverse proxy, Chromium browser | PASS for local TLS only. Explicit HTTPS public URL issued a Secure, HttpOnly, SameSite=Strict cookie invisible to `document.cookie`. Login/reload worked, sign-out cleared the cookie, and retained old-cookie replay returned 401. Login and authenticated views were inspected at 390 and 1280 pixels without horizontal overflow. The ordinary browser rejected the untrusted certificate; a separate ephemeral browser context ignored errors only for this local fixture. Public trust, DNS and operator proxy compatibility remain UNEXECUTED. |
| F | `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`; actual Docker Engine 29.9.0, Compose 5.6.0, pinned Python 3.12.13, SQLite 3.40.1 | PASS current-source recreation and persistence. Both existing app and restored stacks rebuilt and force-recreated with healthy frontend/backend. All 30 application Python files in each running image matched current source hashes. `check-update` passed both complete v1 databases. Real HTTP administrator/member password login, session, profile, portfolio, orders, activity and logout passed. Retained session-row digests and account/game responses matched before/after. The app retained 41 orders, 83 history rows and one held share per user; restore retained 34 orders, 68 history rows and administrator/member quantities two/one. Each retained four aliases, one intervention, closed setup and the additional 64 MiB table. Integrity and foreign keys passed. Both matching backups kept their digests. The restored stack used no Riot key; the app used the controlled external provider. This refresh performed no new backup or restore. |
| N | `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`; actual Podman 5.8.4, podman-compose 1.5.0, normal no-key browser | PASS current-source normal recreation. Both services were healthy, only the frontend published a loopback HTTP port, Gamba remained off, and complete-v1 `check-update` passed. The existing administrator resumed in the rendered browser with cash 1000, two preserved unlinked accounts and usable administrator controls. No new setup or live Riot success was claimed. |
| E | `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`; actual Podman Compose, two independent browser profiles, demo without Riot | PASS current-source demo journey. Healthy explicit demo and complete-v1 preflight passed. Two profiles received distinct IDs, identical shared prices for 12 players and separate balances 1000. A rendered one-share buy reduced only visitor A to 921.19, with one holding/order; visitor B retained 1000 and empty holdings/orders. Reload retained IDs and state. Streamer labels used aliases without demo tags. UI logout removed A's personal user, order, holding and lot rows, leaving only B's user/session. Shared 12 players, 434 history rows and 13 alias assignments remained. Natural thirty-minute cleanup was not rerun at this head; D records that earlier elapsed-time proof, and the cleanup code is unchanged. |

Feature and failure scenarios are retained in [local authentication tests](../backend/tests/test_local_auth.py), [administrator participation tests](../backend/tests/test_admin_participation.py), [demo tests](../backend/tests/test_demo.py), [Riot recovery tests](../backend/tests/test_riot_recovery.py), [controlled-provider process restart tests](../backend/tests/test_riot_restart.py), [online backup tests](../backend/tests/test_operator_backup.py), [supported update tests](../backend/tests/test_supported_updates.py) and [identity presentation tests](../frontend/tests/identityPresentation.test.ts). These cover concurrency, expiry, replay, revocation, rollback and privacy cases without claiming real upstream acceptance.

## Story matrix

Each row uses the current target revision `a9807dc` and references the exact prior evidence revision/provider above. PASS refers to that recorded evidence. F, N and E identify current-head refreshes; rows marked pending retain their earlier narrower proof. The matrix preserves the separate release, upstream and target gaps. All rows still need owner acceptance.

| Story | Scenario | Recorded status | Provider/evidence | Current target evidence |
|---|---|---|---|---|
| 1 | One installation owns one private market. | PASS | P/I/F/N/E | `a9807dc`, PASS normal/demo stacks |
| 2 | Clone a standalone release tag and use supplied configuration. | UNEXECUTED release-tag install | Release owner; [installation procedure](DEPLOYMENT.md#fresh-installation) exists, no standalone tag | `a9807dc`, unreleased |
| 3 | Build and start with Docker Compose. | PASS | Actual Docker Engine/Compose, F | `a9807dc`, PASS build/recreation |
| 4 | Build and start with Podman Compose. | PASS | Actual Podman, N/E; prior P/A/D/U | `a9807dc`, PASS normal/demo recreation |
| 5 | Local images use pinned build inputs. | PASS | Actual builds F/N/E; tracked Containerfiles and lockfiles | `a9807dc`, PASS current source/build |
| 6 | Minimal configuration needs no external auth or tunnel. | PASS | Empty-key normal/restore stacks, N/F | `a9807dc`, PASS no-key access |
| 7 | Configurable HTTP entry point supports LAN or a proxy. | PASS for host and host-to-LAN-address access | P/I/F/N/E; second physical LAN client UNEXECUTED | `a9807dc`, PASS loopback HTTP; remote LAN refresh pending |
| 8 | Operator reverse proxy terminates public HTTPS. | PASS local self-signed fixture; UNEXECUTED public trusted HTTPS | H; deployment operator owns actual target | `a9807dc`, public check pending |
| 9 | Host directory retains SQLite after container replacement. | PASS | F/N/E; prior P/A/B | `a9807dc`, PASS preserved data |
| 10 | Operator log supplies the one-time setup link. | PASS | P and setup integration tests, T | `a9807dc`, refresh pending |
| 11 | Setup closes after creation of the sole administrator. | PASS | F/N; concurrent setup tests, T | `a9807dc`, PASS closed setup; initial setup replay pending |
| 12 | Local username/password login needs no identity provider. | PASS | Actual HTTP F and browser N/E; prior A/P/H | `a9807dc`, PASS normal/demo session access |
| 13 | Account access needs no email. | PASS | F/N/E; T | `a9807dc`, PASS existing account access |
| 14 | Administrator creates member invitations. | PASS | P/A/I; T | `a9807dc`, refresh pending |
| 15 | Invited member chooses their credentials. | PASS | P/I; T | `a9807dc`, refresh pending |
| 16 | Invitation expires after seven days and consumes once. | PASS | Controlled-time/replay SQLite tests, T; actual consumption P/I | `a9807dc`, suite tree matches; runtime refresh pending |
| 17 | Administrator revokes unused invitations. | PASS | HTTPX/SQLite lifecycle tests, T | `a9807dc`, suite tree matches; runtime refresh pending |
| 18 | Normal session lasts seven days. | PASS | Controlled-time tests T; actual retained rows/reload F/N/E | `a9807dc`, PASS retained sessions; seven-day expiry is controlled-time evidence |
| 19 | Logout immediately revokes the current session. | PASS | Current actual HTTP F and demo UI E; old-cookie replay H | `a9807dc`, PASS logout; HTTPS replay refresh pending |
| 20 | Password replacement ends every affected session. | PASS | Multi-session browser/HTTPX, A; races/rollback T | `a9807dc`, refresh pending |
| 21 | Administrator creates one-hour, one-use reset links. | PASS | Browser consumption A; expiry/replay T | `a9807dc`, refresh pending |
| 22 | Administrator revokes unused reset links. | PASS | S and lifecycle tests, T | `a9807dc`, refresh pending |
| 23 | Server CLI recovers the existing administrator. | PASS | Podman getpass and Docker protected stdin, A | `a9807dc`, refresh pending |
| 24 | Riot onboarding is separate from local account access. | PASS controlled external provider; UNEXECUTED live linking | Real adapter/browser I; no-key A; Riot operator owns live check | `a9807dc`, refresh pending |
| 25 | Administrator trades after ordinary Riot onboarding. | PASS controlled external provider; UNEXECUTED live onboarding | Actual browser I; Riot operator owns live check | `a9807dc`, refresh pending |
| 26 | Game information requires authentication. | PASS | T; anonymous/forged-header denial; actual authenticated reads F/N/E | `a9807dc`, suite tree matches; PASS authenticated reads |
| 27 | Successful game interventions are visible to members. | PASS | Real UI intervention/member view I; atomic tests T | `a9807dc`, refresh pending |
| 28 | Activity identifies actor, affected member, time and change. | PASS | I/B/S and transaction tests, T | `a9807dc`, refresh pending |
| 29 | Normal views show username and linked RiotName. | PASS | Recognizable normal data I/S; preserved linked profiles F | `a9807dc`, PASS profile preservation; broad rendered refresh pending |
| 30 | Streamer Mode replaces names with League aliases. | PASS | Broad rendered checks I/S; current demo masked labels E | `a9807dc`, PASS demo labels; broad-view refresh pending |
| 31 | Alias remains stable across views and reloads. | PASS | I/S/B/U; current persisted aliases F and demo reload E | `a9807dc`, PASS persistence/demo reload; broad-view refresh pending |
| 32 | Streamer Mode hides tags and identifying links. | PASS | Broad text/titles/accessible values/links I/S; demo tags E | `a9807dc`, PASS demo masking; broad-view refresh pending |
| 33 | Gamba is disabled by default. | PASS | Current no-key normal/demo N/E; prior API/default/loading checks P/T | `a9807dc`, PASS default-off stacks |
| 34 | Explicit opt-in enables private Gamba. | PASS | P/S and existing Gamba tests, T | `a9807dc`, refresh pending |
| 35 | Missing/rejected Riot key does not block login/admin. | PASS | Current no-key actual stacks F/N/E; controlled rejection T | `a9807dc`, PASS no-key access; rejected-key is test evidence |
| 36 | UI explains unavailable Riot configuration. | PASS | No-key browser P/A; controlled 503 I; error tests T | `a9807dc`, refresh pending |
| 37 | Failed Riot refresh changes no prices. | PASS controlled provider; UNEXECUTED live outage behavior | Actual scheduled failed refresh I; transaction tests T | `a9807dc`, refresh pending |
| 38 | Replace key and recreate containers without reinstalling. | PASS controlled retry/environment recreation; UNEXECUTED live key replacement | T changed-key process restart; I controlled retry; F/N recreation | `a9807dc`, PASS recreation; live key recovery UNEXECUTED |
| 39 | Live backup includes coherent WAL state during writes. | PASS | Actual Podman/Docker operator and HTTP writes, B/U | `a9807dc`, refresh pending |
| 40 | Fresh restore recovers accounts and coherent game state. | PASS | Prior fresh restore B/U; current restored-instance preservation F | `a9807dc`, PASS restored state preserved; no new restore performed |
| 41 | Update actual supported standalone releases. | UNEXECUTED, first-release predecessor exception | Current-v1 F/N/E; development-artifact U; next release owner | `a9807dc`, PASS complete-v1 preflight; no released predecessor |
| 42 | Recover failed update with old release and matching backup. | PASS development/synthetic failure; UNEXECUTED released predecessor recovery | Exact old development artifact and snapshot U; next release owner owns released scenario | `a9807dc`, released scenario pending |
| 43 | Explicit environment flag loads demo automatically. | PASS | Current explicit demo E; prior seed startup P/D; T | `a9807dc`, PASS current demo flag/market |
| 44 | Demo runs without a Riot key. | PASS | Actual no-key current demo E | `a9807dc`, PASS no-key demo |
| 45 | `demo/demo` login creates a trial session. | PASS | Two independent current browser profiles E | `a9807dc`, PASS two demo logins |
| 46 | Visitors have separate balance, holdings and orders. | PASS | Current rendered trade/isolation E; guessed-resource denial D/T | `a9807dc`, PASS separate state; denial is D/T evidence |
| 47 | Visitors share simulated prices and tracked players. | PASS | Current two-profile shared prices E | `a9807dc`, PASS shared market |
| 48 | Reload preserves valid demo identity and state. | PASS | Current browser reload E | `a9807dc`, PASS identity/state retained |
| 49 | Logout immediately deletes personal demo state. | PASS | Current UI sign-out and physical SQLite row check E | `a9807dc`, PASS immediate deletion |
| 50 | Thirty-minute inactivity ends access and triggers cleanup. | PASS | Actual elapsed thirty-minute D; unchanged cleanup code; T | `a9807dc`, controlled-time suite matches; natural wait not rerun |
| 51 | Cleanup preserves the shared market. | PASS | Current logout row counts E; natural idle D; regular-user T | `a9807dc`, PASS shared state after logout; idle proof D |
| 52 | Demo visitors have no administrator permissions. | PASS | Mode/permission API tests T; actual current demo UI E | `a9807dc`, suite tree matches; PASS demo UI |

## Reproduction and completion

Use the documented [Compose install](DEPLOYMENT.md#fresh-installation), [password recovery](DEPLOYMENT.md#change-and-recover-passwords), [live backup/fresh restore](DEPLOYMENT.md#live-backup-and-fresh-restore), [supported update/recovery](DEPLOYMENT.md#supported-standalone-updates-and-failed-update-recovery) and [separate demo deployment](DEPLOYMENT.md#demo-and-optional-gamba) procedures. Keep setup links, credentials, `.env`, cookies and backups in protected operator storage. Evidence records references and outcomes, never their values.

Run required backend checks from `backend/`:

```bash
uv run ruff check .
uv run ruff format .
uv run pytest -v
```

Run required frontend checks from `frontend/`:

```bash
corepack pnpm@10.34.7 run lint
corepack pnpm@10.34.7 run format
corepack pnpm@10.34.7 run build
node --test tests/identityPresentation.test.ts
```

After the pending review/fix, final refresh must identify the actual source inside each built image, Git head/base/working diff, runtime and scenario. Record current-head test counts, formatting/build results, the independent standards/spec review, GitHub CI revision and any unresolved failures. Check the final documentation diff and links. A green health endpoint alone does not establish account or game preservation.

The public trusted HTTPS/browser journey, live Riot linking/refresh/key replacement, published release-tag installation and released predecessor update remain UNEXECUTED. Their absence limits claims of complete deployment acceptance. The first-release predecessor exception is explicit; it does not waive the next release's update/recovery proof. Touch and assistive-technology behavior were not tested. No owner acceptance, merged delivery or release publication is claimed.
