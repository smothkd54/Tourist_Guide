# GitVerse — primary repository and CI

GitVerse is the primary home for this project; GitHub stays as a mirror while
the demo is being prepared. This page records the setup steps and the parts
that have **not** been done yet.

> **Status:** the account is `smothkd`, the repository is imported at
> <https://gitverse.ru/smothkd/Tourist_Guide>, and this clone uses
> `origin` = GitVerse (SSH) and `github` = the GitHub mirror. The first
> GitVerse pipeline run is still pending. The import did not carry the Git LFS
> objects; they were uploaded separately (see “Large LFS objects” below).

## Why GitVerse

- Free public repositories and CI, no payment method.
- Git LFS quota covers this repository (the model is ~8.4 MB and the published
  thumbnails are ~17 MB).
- CI runners are reachable from the venue network, unlike the Render/Neon
  free tier tested for the demo.
- The platform is the assignment's requested hosting target.

## 1. Create the account and import the repository

Completed on 2026-11-08 with the login `smothkd`. The steps are kept as a
record:

1. Sign up at <https://gitverse.ru> and confirm the email address.
2. Choose **Import repository** (Импорт репозитория) and paste the GitHub URL:
   `https://github.com/smothkd54/Tourist_Guide.git`.
3. Import **full history**, not a snapshot. The `.gitattributes` file already
   declares `data/photos/*` and `models/*` as LFS paths — but the import does
   **not** copy the LFS objects themselves (see section 2).
4. Name the repository `Tourist_Guide`.
5. Do **not** enable GitVerse-side mirroring from GitHub: this clone pushes to
   both remotes explicitly.

## 2. Point the local clone at both remotes

This clone is already configured:

```
github  https://github.com/smothkd54/Tourist_Guide.git (fetch)
github  https://github.com/smothkd54/Tourist_Guide.git (push)
origin  git@gitverse.ru:smothkd/Tourist_Guide.git (fetch)
origin  git@gitverse.ru:smothkd/Tourist_Guide.git (push)
```

For reference, that was set up with:

```bash
git remote rename origin github
git remote add origin git@gitverse.ru:smothkd/Tourist_Guide.git
git fetch origin
git branch --set-upstream-to=origin/main main
```

Authentication is SSH: the key `kadeiemi@sfedu.ru` is registered on GitVerse as
`smothkd`. The local, gitignored `.gitconfig-gitverse` file carries the commit
identity, a Windows Credential Manager helper for a possible HTTPS fallback,
and the LFS setting described below. It is included with:

```bash
git config --local include.path ../.gitconfig-gitverse
```

The imported `main` already matched the local `HEAD` (`c95edd2`), so no rebase
was needed. Pushing this clone updates GitVerse; pushing `github` updates the
mirror.

### Large LFS objects

The import copied the commits but not the LFS blobs, so a clone initially
failed its checkout. Uploading repaired it:

```bash
git lfs push --all origin
```

The photos and the 8.8 MB TFLite model went through the hybrid HTTPS path, but
the 33 MB `models/landmark_classifier.keras` returned `403 Forbidden` from the
storage CDN. GitVerse accepts it over the pure SSH transfer, so the clone
forces that protocol for GitVerse only:

```bash
git config lfs.https://gitverse.ru/.sshtransfer always
```

The same setting lives in `.gitconfig-gitverse`. Do not set it globally: GitHub
does not implement the pure SSH protocol and its LFS uploads would break.

Verification was a fresh `--depth 1` clone of `main`; it checked out 40 LFS
files and produced the real sizes:

```
models/landmark_classifier.tflite   8,797,436
models/landmark_classifier.keras   33,004,242
data/photos/chekhov_monument.jpg      749,587
```

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

- [x] Account created and email confirmed (`smothkd`).
- [x] Repository imported with full history; LFS objects uploaded separately.
- [x] `origin` points at GitVerse; `github` points at the mirror.
- [x] `git lfs ls-files` lists the model and thumbnails, and a fresh clone
      resolves all 40 LFS files to their real sizes.
- [ ] First `CI` run is green in the GitVerse UI.
- [x] `/` on the local composed instance reports `data_source: postgres`.
- [ ] Branch protection requires the `CI` workflow.
- [x] README clone URL and CI section no longer claim GitHub is primary.

After the checklist is complete, remove the duplicate backend job from
`.github/workflows/ci.yml` (keep the Android build and Trivy jobs) and keep
`photo-audit.yml` (Wikimedia is unreachable from the developer's network, so
the audit still needs a runner with outbound access).
