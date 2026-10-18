# Issue tracker: GitHub

Issues and specs for this repository live as GitHub Issues. Use the `gh` CLI for operations and infer the repository from `git remote -v`.

## Conventions

- Create: `gh issue create --title "..." --body-file <file>`.
- Read: `gh issue view <number> --comments`, including labels when triaging.
- List: `gh issue list` with explicit state and label filters.
- Comment: `gh issue comment <number> --body-file <file>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close: `gh issue close <number> --comment "..."`.

Use body files for multiline or Thai content so shell quoting does not alter the text.

## Pull requests as a triage surface

**PRs as a request surface: no.** Pull requests are not included in the issue triage queue.

GitHub shares one number space across issues and pull requests. Resolve an ambiguous number with `gh pr view <number>` and fall back to `gh issue view <number>`.

## Skill vocabulary

- When a skill says **publish to the issue tracker**, create a GitHub issue.
- When a skill says **fetch the relevant ticket**, read the GitHub issue and its comments.
- Apply the state labels defined in `docs/agents/triage-labels.md`.

## Wayfinding

When a skill creates a map and child tickets, prefer GitHub sub-issues and native issue dependencies. If either feature is unavailable, use a task list in the map issue and a `Blocked by: #<number>` line in the child issue.
