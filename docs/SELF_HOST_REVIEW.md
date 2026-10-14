# Standalone self-host review

Independent reviewers examined the standalone change against fixed base `e7280b4c79fe056c77407ae576e39446d19b4792`. The initial clean integration was `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`. Both axes reviewed the documentation refresh at `5d497f8` and the corrections through clean candidate `8a820a52140856fc89d25b9165da5a39d9ed1c2d` on 2026-10-14. Integration `39dceae6f647fd89818381832607acb2f1f86810` has exactly the same backend, frontend, tests and Compose configuration as that candidate. The integration diff changes acceptance documentation only.

## Standards

The initial review found one documented policy mismatch: CSRF rejection bypassed the common no-store/no-referrer response headers. It also identified duplicated invitation/reset revocation, secret-link delivery and Riot-status classification as maintainability concerns.

The corrections apply headers to rejection responses, extract a typed auth-owned conditional revocation helper, share secret-link rendering and clipboard feedback, and use one typed Riot-unavailable predicate. Routes retain authorization and lifecycle responsibilities. Link delivery adds no durable secret storage. The final affected-code review reapplied the complete Fowler baseline and found zero remaining documented-standard violations or material new smells. The signed League Points correction retains strict integer validation and the accepted signed numeric domain.

## Spec

The initial review found a P2 defect: malformed Riot match responses could change prices and mark a failed refresh successful. The adapter now validates consumed upstream response shapes and returns a typed unavailable error. The scheduler rolls back the complete refresh before price/history commit or success-timestamp assignment. Valid empty match history retains the existing aggregate-pricing behavior and formula.

The final affected-code review found zero unresolved Spec findings or scope additions. Signed League Points remain supported. Test status isolation resolved the earlier order-dependent focused failure without changing production behavior. Operator guidance specifies full Compose recreation, and the demo footer describes its configured simulated cadence and committed timestamp.

Both axes also reviewed the later layout corrections through clean source `1d256a5acce205fd84f4814649a377d6cc007cbd`, integrated with an identical tree at `6b9037e01aa6756d54a69930ee5bc69d006fc160`. The reset selector uses the available mobile width. The Poro-history grid and card contain the existing table scroller. These changes preserve behavior and component responsibilities. Both axes found zero remaining findings. Pinned frontend lint, format and build passed; rebuilt Docker and Podman browser checks passed at 390 and 1280 pixels. The backend, tests and Compose files still match the completed candidate.

Both review axes inspected evidence without rerunning the complete runtime journeys. The completed exact-candidate suite reports 307 passes and one optional live Riot skip; exact-integration CI passed at `39dceae`. [Acceptance evidence](SELF_HOST_ACCEPTANCE.md) records the later checks and unreplayed journeys. The final documentation commit has its own CI record on [PR #41](https://github.com/KyleDerZweite/nashordaq/pull/41/checks). Owner acceptance and live Riot evidence remain separate from these code reviews. The installation contract uses a git clone of `main` and commit-based updates. The merged dependency maintenance and its targeted runtime proof are recorded separately in the acceptance record.
