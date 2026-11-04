# GitVerse — primary repository and CI

GitVerse is the primary home for this project; GitHub stays as a mirror while
the demo is being prepared. This page records the setup steps and the parts
that have **not** been done yet.

> **Status:** the workflow and documentation are in the repository, but the
> GitVerse account, the repository import and the first push have not happened.
> They need the account owner's browser session. Replace `<login>` with the
> GitVerse username once the account exists.

## Why GitVerse

- Free public repositories and CI, no payment method.
- Git LFS quota covers this repository (the model is ~8.4 MB and the published
  thumbnails are ~17 MB).
- CI runners are reachable from the venue network, unlike the Render/Neon
  free tier tested for the demo.
- The platform is the assignment's requested hosting target.

## 1. Create the account and import the repository

1. Sign up at <https://gitverse.ru> and confirm the email address.
2. Choose **Import repository** (Импорт репозитория) and paste the GitHub URL:
   `https://github.com/smothkd54/Tourist_Guide.git`.
3. Import **full history**, not a snapshot, and keep Git LFS enabled. The
   `.gitattributes` file already declares `data/photos/*` and `models/*.tflite`
   as LFS paths.
4. Name the repository `Tourist_Guide` (the exact name is not important; the
   commands below assume it).
5. Do **not** enable GitVerse-side mirroring from GitHub yet. Push once from
   the working copy first, then decide which direction mirrors.

## 2. Point the local clone at both remotes

The current clone still has `origin` on GitHub. Rename it to `github`, then add
GitVerse as `origin` so the primary push goes to the right place:

```bash
git remote rename origin github
git remote add origin https://gitverse.ru/<login>/Tourist_Guide.git
git remote -v
```

Expected:

```
github  https://github.com/smothkd54/Tourist_Guide.git (fetch)
github  https://github.com/smothkd54/Tourist_Guide.git (push)
origin  https://gitverse.ru/<login>/Tourist_Guide.git (fetch)
origin  https://gitverse.ru/<login>/Tourist_Guide.git (push)
```

Push the current history and the LFS objects:

```bash
git lfs push --all origin
git push -u origin main
```

GitVerse asks for a username and a personal access token, not the account
password. Create the token under **Settings → Access tokens** with `repo`
scope.

If the import already brought the history in, the first push will be rejected
as non-fast-forward. That is expected: check out the imported branch, rebase
the local commits on it, then push again.

## 3. Branch protection

Protect `main` under **Settings → Branches**:

- no direct pushes;
- at least one approving review for a merge request;
- the `CI` workflow must pass before merge;
- linear history (squash or rebase) is preferred.

The repository is developed by one person, so the review rule can be disabled
for the demo. Keep the CI requirement in place either way.

## 4. CI pipeline

`.gitverse/workflows/ci.yaml` has two jobs:

| Job | What it proves |
|-----|----------------|
| `backend` | ruff is clean; the suite passes in JSON fallback mode; PostgreSQL 16 installs, migrates and seeds; the suite passes again in PostgreSQL mode |
| `docker` | the serving image builds; the entrypoint runs preflight; the container answers `/` with `data_source: json` and serves all 46 landmarks |

GitVerse also scans `.github/workflows/*.yaml`, but this repository's GitHub
workflow uses `.yml`, so it is not executed here. The GitVerse workflow is
self-contained; the GitHub file only runs on GitHub.

### Limits that shaped the pipeline

| Limit | Value | Consequence |
|-------|-------|-------------|
| Job time | 30 minutes | The Android Gradle build is not in the GitVerse pipeline; it stays on GitHub |
| Cloud runner default timeout | 15 minutes | Every job sets `timeout-minutes: 30` explicitly |
| Public CI minutes | 1000 per month | One push runs both jobs; do not add a matrix of Python versions |
| Artifacts | 500 MB | No APK or model artifacts are uploaded |
| Git LFS | 2 GB/month, 100 MB/file over HTTP | The model and thumbnails fit; training images stay untracked |

The backend job installs PostgreSQL with `apt` instead of `services:`. The
service-container syntax is GitHub-specific and is not documented for GitVerse.

## 5. Mirror to GitHub

Two equivalent options:

**Option A — two remotes (chosen for the demo).** Push to both explicitly:

```bash
git push github main
git push origin main
```

**Option B — GitVerse mirroring.** In the GitVerse repository settings, enable
mirroring to the GitHub URL with a GitHub personal access token. This keeps the
mirror current without a second push, but it makes GitHub a downstream copy:
issues and pull requests must stay on GitVerse.

Either way, GitHub keeps the Android build job and the photo-attribution audit.
The GitHub workflow is deliberately kept until the first green GitVerse run.

## 6. Verification checklist

- [ ] Account created and email confirmed.
- [ ] Repository imported with full history and LFS objects.
- [ ] `origin` points at GitVerse; `github` points at the mirror.
- [ ] `git lfs ls-files` lists the model and thumbnails on both remotes.
- [ ] First `CI` run is green in the GitVerse UI.
- [ ] `/` on the deployed instance reports `data_source: postgres`.
- [ ] Branch protection requires the `CI` workflow.
- [ ] README clone URL and CI section no longer claim GitHub is primary.

After the checklist is complete, remove `.github/workflows/ci.yml` and keep
`photo-audit.yml` (Wikimedia is unreachable from the developer's network, so
the audit still needs a runner with outbound access).
