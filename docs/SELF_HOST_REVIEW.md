# Standalone self-host review

Independent reviewers examined the standalone change against fixed base `e7280b4c79fe056c77407ae576e39446d19b4792`. The initial clean integration was `a9807dc0cb5154475d90d9aba2fdadfecfe4551f`. Both axes reviewed the documentation refresh at `5d497f8` and the corrections through clean candidate `8a820a52140856fc89d25b9165da5a39d9ed1c2d` on 2026-10-14. Integration `39dceae6f647fd89818381832607acb2f1f86810` has exactly the same backend, frontend, tests and Compose configuration as that candidate. The integration diff changes acceptance documentation only.

## Standards

The initial review found one documented policy mismatch: CSRF rejection bypassed the common no-store/no-referrer response headers. It also identified duplicated invitation/reset revocation, secret-link delivery and Riot-status classification as maintainability concerns.

The corrections apply headers to rejection responses, extract a typed auth-owned conditional revocation helper, share secret-link rendering and clipboard feedback, and use one typed Riot-unavailable predicate. Routes retain authorization and lifecycle responsibilities. Link delivery adds no durable secret storage. The final affected-code review reapplied the complete Fowler baseline and found zero remaining documented-standard violations or material new smells. The signed League Points correction retains strict integer validation and the accepted signed numeric domain.

## Spec

The initial review found a P2 defect: malformed Riot match responses could change prices and mark a failed refresh successful. The adapter now validates consumed upstream response shapes and returns a typed unavailable error. The scheduler rolls back the complete refresh before price/history commit or success-timestamp assignment. Valid empty match history retains the existing aggregate-pricing behavior and formula.

The final affected-code review found zero unresolved Spec findings or scope additions. Signed League Points remain supported. Test status isolation resolved the earlier order-dependent focused failure without changing production behavior. Operator guidance specifies full Compose recreation, and the demo footer describes its configured simulated cadence and committed timestamp.

Both review axes inspected evidence without rerunning the complete runtime journeys. The completed exact-candidate suite reports 307 passes and one optional live Riot skip; exact-integration CI passed. [Acceptance evidence](SELF_HOST_ACCEPTANCE.md) records targeted runtime checks and unreplayed journeys. Owner acceptance, live Riot, public trusted HTTPS and release-artifact checks remain separate. No release or deployment is authorized by these reviews.
