# Governance

How the project is run: contributing rules, conduct, security, and the
changelog. The templates powering PR/issue flows live in `.github/`.

| # | Page | Purpose |
|---|---|---|
| [01-contributing](01-contributing.md) | How to contribute: quick start, project layout, PR checklist, bug reporting | Contributor guide |
| [02-code-of-conduct](02-code-of-conduct.md) | Contributor Covenant 2.1 adaptation | Conduct |
| [03-security-policy](03-security-policy.md) | Supported versions, private vulnerability reporting, scope | Security |
| [04-changelog](04-changelog.md) | Keep a Changelog, semantic versions | Release history |

Related GitHub configuration:

- `.github/pull_request_template.md` — the PR body/checklist every contributor
  starts from.
- `.github/ISSUE_TEMPLATE/bug_report.yml` — asks for the exact command,
  full output, versions, and `localcaption doctor`.
- `.github/ISSUE_TEMPLATE/feature_request.yml` — keeps proposals inside the
  "thin local orchestrator" scope.
- `.github/ISSUE_TEMPLATE/config.yml` — points discussion/security to the
  right places.
- `.github/workflows/` — `ci.yml` (test matrix + lint) and `release.yml`
  (OIDC publish — see [../operations/03-releasing.md](../operations/03-releasing.md)).

Template: [template.md](template.md) (canonical copy: [../template.md](../template.md)).