# Releasing

Pushing a `v*` tag is the whole release. `.github/workflows/release.yml` then:

1. Writes the tag's version into `custom_components/etsyapp/manifest.json`
2. Builds `etsyapp.zip` (what HACS installs)
3. Publishes the GitHub release with notes grouped from conventional commits

Tags containing a `-` (e.g. `v1.4.0-beta.1`) are published as pre-releases.
Stable notes cover everything since the last stable tag; pre-release notes
cover everything since the previous tag of any kind.

Don't bump `manifest.json` by hand and don't create releases in the GitHub UI.

## Branches

- `beta` — day-to-day work; direct pushes are fine
- `main` — what stable users run; only updated by merging `beta`

## Beta release

```bash
git checkout beta && git pull
git tag v1.4.0-beta.1
git push origin v1.4.0-beta.1
```

## Stable release

```bash
# 1. Promote beta to main
gh pr create --base main --head beta --title "feat: release 1.4.0" --body "..."
# wait for CI, then merge with a merge commit (not squash), so beta and main stay in sync
gh pr merge --merge

# 2. Tag main
git checkout main && git pull
git tag v1.4.0
git push origin v1.4.0
```

PR titles must use a conventional-commit prefix (`feat:`, `fix:`, `chore:`, ...).

## Fixing a bad release

Delete the release and tag, fix, and re-tag:

```bash
gh release delete v1.4.0 --cleanup-tag --yes
```

Avoid this once users may have installed the release; prefer a patch release.
