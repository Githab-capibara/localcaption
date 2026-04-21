# Releasing localcaption

This project uses GitHub Actions + **PyPI Trusted Publishing (OIDC)** to
release new versions. No PyPI tokens are stored anywhere.

## One-time setup

Do this **once** before the first release. About 5 minutes.

### 1. Register the project on PyPI and TestPyPI

Both registries need to know about the project before they can accept a
"pending publisher" claim. Easiest path: create the projects manually with
a placeholder upload, or use Trusted Publishing's "pending publisher" flow
(no upload needed).

This guide uses the **pending publisher** flow because it requires zero
prior uploads.

### 2. Configure Trusted Publishing on **TestPyPI**

1. Sign in to <https://test.pypi.org> (create the account if needed).
2. Go to **Account settings → Publishing → Add a new pending publisher**.
3. Fill in:
   - **PyPI Project Name:** `localcaption`
   - **Owner:** `jatinkrmalik`
   - **Repository name:** `localcaption`
   - **Workflow name:** `release.yml`
   - **Environment name:** `testpypi`
4. Click **Add**.

### 3. Configure Trusted Publishing on **PyPI** (production)

Repeat step 2 at <https://pypi.org> with one difference:
- **Environment name:** `pypi`

### 4. Create matching GitHub environments

The workflow gates each publish job behind a GitHub Environment so you can
add manual approval if you ever want a "human in the loop" step.

In the repo: **Settings → Environments → New environment**, twice:
- `testpypi` (no protection rules needed)
- `pypi` (optional: add yourself as a required reviewer for an extra
  "are you sure?" step on every release)

That's it for one-time setup.

## Cutting a release

```bash
# 1. Make sure main is green and all the changes you want are merged.
git checkout main
git pull

# 2. Bump version in pyproject.toml (X.Y.Z, no leading 'v').
$EDITOR pyproject.toml

# 3. Move the [Unreleased] block in CHANGELOG.md under a new [X.Y.Z] header.
$EDITOR CHANGELOG.md

# 4. Commit and push.
git add pyproject.toml CHANGELOG.md
git commit -m "chore(release): X.Y.Z"
git push origin main

# 5. Tag and push.
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The push of the `v*` tag triggers `.github/workflows/release.yml`, which:

1. **build** — produces `dist/*.whl` + `dist/*.tar.gz`, runs `twine check
   --strict`, and verifies that `pyproject.toml` version matches the tag.
2. **publish-testpypi** — uploads to <https://test.pypi.org>. If anything
   is wrong with the metadata, the release stops here and PyPI is untouched.
3. **publish-pypi** — uploads to <https://pypi.org>. Only runs after
   TestPyPI succeeded.
4. **github-release** — creates a GitHub Release page with auto-generated
   notes and the wheel + sdist attached.

About 2–3 minutes end to end.

## Verifying a release

After CI goes green:

```bash
# Real PyPI
pip index versions localcaption

# Install in a throwaway env
pipx install --force --suffix=-test localcaption
localcaption-test --version
```

## Recovering from a bad release

PyPI does **not** allow re-uploading the same version, even if you delete
it. The recipe is:

1. Yank the bad version on pypi.org (Project page → Manage → Yank). Yanked
   versions remain installable by exact pin but are hidden from `pip install
   localcaption` resolvers.
2. Bump to the next patch version.
3. Tag and push as normal.
