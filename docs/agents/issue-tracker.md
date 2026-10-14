# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `KyleDerZweite/nashordaq`.
Use the `gh` CLI from this clone.

## Conventions

- Create an issue with `gh issue create --title "..." --body-file <file>`.
- Read an issue with `gh issue view <number> --comments`.
  Fetch its labels with `gh issue view <number> --json labels`.
- List issues with `gh issue list --state open --json number,title,body,labels,comments`.
  Apply label and state filters as needed.
- Comment with `gh issue comment <number> --body-file <file>`.
- Apply or remove labels with `gh issue edit <number> --add-label "..."`
  or `--remove-label "..."`.
- Close an issue with `gh issue close <number>`.

Write multiline bodies to a temporary file and pass `--body-file`.
Infer the repository from `git remote -v`; `gh` does this automatically.

## Pull requests as a triage surface

PRs as a request surface: no.

If this flag changes to `yes`, triage external PRs using the same labels
and states as issues. Use `gh pr view`, `gh pr diff`, `gh pr list`,
`gh pr comment`, `gh pr edit`, and `gh pr close`.
Include authors with association `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`,
or `NONE`; exclude `OWNER`, `MEMBER`, and `COLLABORATOR`.

GitHub shares issue and PR numbers. Resolve ambiguous references with
`gh pr view <number>`, falling back to `gh issue view <number>`.

## Skill operations

When a skill says "publish to the issue tracker", create a GitHub issue.
When it says "fetch the relevant ticket", read the issue and its comments.

## Wayfinding operations

The map is one issue labelled `wayfinder:map`, containing Notes,
Decisions-so-far, and Fog. Child tickets use labels `wayfinder:<type>`,
where type is `research`, `prototype`, `grilling`, or `task`.

Link children using GitHub sub-issues. If unavailable, list children in
the map's task list and add `Part of #<map>` to each child.

Represent blockers with native GitHub issue dependencies:

`gh api --method POST repos/KyleDerZweite/nashordaq/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`

Get the blocker's database ID with
`gh api repos/KyleDerZweite/nashordaq/issues/<number> --jq .id`.
Use this ID, not its issue number or node ID.
If dependencies are unavailable, add `Blocked by: #<number>` to the child.

For the frontier, consider open children in map order.
Exclude assigned tickets and tickets with open blockers.
Use `issue_dependencies_summary.blocked_by` where available;
otherwise inspect the issues in the `Blocked by` line.

Claim with `gh issue edit <number> --add-assignee @me` as the first write.
Resolve by commenting with the answer, closing the child, and adding
a gist and link to the map's Decisions-so-far.
