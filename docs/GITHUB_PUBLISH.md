# GitHub publish flow — Termux

Target repository: `duyuyd/MEGA-CHECKER-ULTIMATE` (existing repository only).

## Run

```bash
bash scripts/publish_github_termux.sh
```

Requirements: `git`, `gh`, and an authenticated GitHub CLI session. The script verifies that the exact target repository is visible before touching Git.

## Safety guarantees

- Never calls `gh repo create`; it cannot create a second repository.
- Never changes repository visibility and never uses `git push --force`.
- If the current directory is already a Git clone, the `origin` URL and current branch must match the target repository/default branch. The local history must contain the currently fetched remote head.
- If the current directory has no `.git`, the script clones the existing target repository, overlays the project source, creates a normal commit and fast-forward pushes. On success it attaches that clone's `.git` metadata to the current project directory.
- Local datasets, generated audit reports, databases, logs, environment files, account-combo files, cookies, tokens and non-test key files are excluded or block the staged publish.
- `PROJECT_FILES.txt` and `checksums.sha256` are regenerated immediately before commit.

## Stop conditions

The script stops without pushing if the target repository is not visible, the remote points elsewhere, the local branch differs from the GitHub default branch, the remote history has moved ahead/diverged, or a protected local-data path is staged. It does not try to resolve a diverged history automatically.
