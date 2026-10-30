#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/bin" "$TMP/home" "$TMP/source/scripts" "$TMP/seed"
git init --bare "$TMP/remote.git" >/dev/null
git init -b main "$TMP/seed" >/dev/null
git -C "$TMP/seed" config user.name seed
git -C "$TMP/seed" config user.email seed@example.invalid
printf 'original\n' > "$TMP/seed/README.md"
git -C "$TMP/seed" add README.md
git -C "$TMP/seed" commit -m seed >/dev/null
git -C "$TMP/seed" remote add origin "$TMP/remote.git"
git -C "$TMP/seed" push -u origin main >/dev/null
SEED_SHA="$(git -C "$TMP/seed" rev-parse HEAD)"

cp "$ROOT/scripts/publish_github_termux.sh" "$TMP/source/scripts/"
cat > "$TMP/source/.gitignore" <<'EOF'
.env
.env.*
dataset_*.txt
random_combo_*.txt
*.db
*.log
EOF
printf 'updated source\n' > "$TMP/source/README.md"
printf 'safe source fixture\n' > "$TMP/source/source.py"
printf 'test data must stay local\n' > "$TMP/source/dataset_100000.txt"
printf 'SECRET=do-not-publish\n' > "$TMP/source/.env"

cat > "$TMP/bin/gh" <<'EOF'
#!/bin/bash
set -Eeuo pipefail
case "$1 $2" in
  "auth status"|"auth setup-git") exit 0 ;;
  "repo view")
    printf '%s\n' '{"nameWithOwner":"duyuyd/MEGA-CHECKER-ULTIMATE","isPrivate":true,"defaultBranchRef":{"name":"main"},"url":"https://github.com/duyuyd/MEGA-CHECKER-ULTIMATE"}'
    ;;
  "repo clone")
    destination="$4"
    git clone --single-branch --branch main "$FAKE_GH_REMOTE" "$destination" >/dev/null
    ;;
  "api user")
    if [[ "${4:-}" == ".login" ]]; then echo test-user; else echo 123456; fi
    ;;
  *) echo "Unexpected gh command: $*" >&2; exit 99 ;;
esac
EOF
chmod +x "$TMP/bin/gh"

PATH="$TMP/bin:$PATH" FAKE_GH_REMOTE="$TMP/remote.git" HOME="$TMP/home" \
  bash "$TMP/source/scripts/publish_github_termux.sh" >/dev/null

NEW_SHA="$(git --git-dir="$TMP/remote.git" rev-parse refs/heads/main)"
[[ "$NEW_SHA" != "$SEED_SHA" ]]
git --git-dir="$TMP/remote.git" cat-file -e "main:source.py"
if git --git-dir="$TMP/remote.git" ls-tree -r --name-only main | grep -Eq 'dataset_100000\.txt|\.env$'; then
  echo '[FAIL] Private local material was published.' >&2
  exit 1
fi
[[ -d "$TMP/source/.git" ]]
[[ -z "$(git -C "$TMP/source" status --porcelain)" ]]
echo 'GITHUB PUBLISH DRY-RUN: PASS'
