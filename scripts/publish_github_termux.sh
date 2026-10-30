#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

# Safely sync this working tree to the EXISTING private project repository.
# Never creates a new repository and never force-pushes.
SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="duyuyd/MEGA-CHECKER-ULTIMATE"
cd "$SOURCE_ROOT"

say() { printf '\n%s\n' "$*"; }
die() { printf '\n[STOP] %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 || die "Chưa có Git. Chạy: pkg install git -y"
command -v gh  >/dev/null 2>&1 || die "Chưa có GitHub CLI. Chạy: pkg install gh -y"
command -v python >/dev/null 2>&1 || die "Không tìm thấy Python trong Termux."

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  say "GitHub CLI chưa đăng nhập. Mở quy trình xác thực chính thức..."
  gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key
fi
gh auth status --hostname github.com >/dev/null 2>&1 || die "GitHub CLI chưa xác thực thành công."
gh auth setup-git --hostname github.com

# Read-only check: target must already exist and be visible to this account.
REPO_JSON="$(gh repo view "$TARGET_REPO" --json nameWithOwner,isPrivate,defaultBranchRef,url 2>/dev/null)" \
  || die "Tài khoản GitHub hiện tại không nhìn thấy $TARGET_REPO. Không tạo repo mới và không push sang repo khác. Kiểm tra đúng tài khoản/quyền truy cập."
REPO_NAME="$(printf '%s' "$REPO_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["nameWithOwner"])')"
BRANCH="$(printf '%s' "$REPO_JSON" | python -c 'import json,sys; d=json.load(sys.stdin); print((d.get("defaultBranchRef") or {}).get("name") or "")')"
REPO_URL="$(printf '%s' "$REPO_JSON" | python -c 'import json,sys; print(json.load(sys.stdin)["url"])')"
IS_PRIVATE="$(printf '%s' "$REPO_JSON" | python -c 'import json,sys; print(str(json.load(sys.stdin)["isPrivate"]).lower())')"
[[ "$REPO_NAME" == "$TARGET_REPO" ]] || die "GitHub trả về repository không khớp: $REPO_NAME"
[[ -n "$BRANCH" ]] || die "Repository chưa có default branch. Không tự khởi tạo lịch sử từ xa."
[[ "$IS_PRIVATE" == "true" ]] || die "Repository không còn ở chế độ PRIVATE. Đã dừng để tránh công khai source ngoài ý muốn."
say "Đích đã xác nhận: $REPO_URL"
say "Default branch: $BRANCH | Private: $IS_PRIVATE"

# Refuse accidental inclusion of local datasets, reports, databases, or secrets.
configure_git_identity() {
  local current_name current_email login user_id
  current_name="$(git -C "$WORK" config user.name || true)"
  current_email="$(git -C "$WORK" config user.email || true)"
  if [[ -z "$current_name" || -z "$current_email" ]]; then
    login="$(gh api user --jq '.login')"
    user_id="$(gh api user --jq '.id')"
    [[ -n "$login" && -n "$user_id" ]] || die "Không lấy được GitHub commit identity."
    [[ -n "$current_name" ]] || git -C "$WORK" config user.name "$login"
    [[ -n "$current_email" ]] || git -C "$WORK" config user.email "${user_id}+${login}@users.noreply.github.com"
  fi
}

check_staged_paths() {
  STAGED_PATHS="$(git -C "$WORK" diff --cached --name-only --diff-filter=ACMR)" python - <<'PY'
import os, sys
paths = os.environ.get("STAGED_PATHS", "").splitlines()
bad = []
for raw in paths:
    p = raw.replace('\\', '/')
    name = p.rsplit('/', 1)[-1].lower()
    parts = [x.lower() for x in p.split('/')]
    if name == '.env' or name.startswith('.env.'):
        bad.append(raw); continue
    if name.endswith(('.db', '.sqlite', '.sqlite3', '.db-wal', '.db-shm', '.log', '.eml', '.csv')):
        bad.append(raw); continue
    if name.startswith(('dataset_', 'random_combo_', 'combo_', 'accounts', 'credentials', 'passwords', 'secrets', 'cookies', 'tokens', 'mega_cache', 'mega_results', 'root_report')):
        bad.append(raw); continue
    if (name.startswith(('audit_', 'dataset_', 'root_report')) or '_report' in name) and name.endswith('.json'):
        bad.append(raw); continue
    if name in {'emails.txt', 'email_list.txt', 'combos.txt'}:
        bad.append(raw); continue
    if name.endswith(('.key', '.p12', '.pfx')):
        bad.append(raw); continue
    if name.endswith('.pem') and not (parts[:2] == ['tests', 'fixtures'] and name.startswith('dkim_test_')):
        bad.append(raw); continue
if bad:
    print('[BLOCKED] Các đường dẫn có khả năng chứa dữ liệu riêng tư:', file=sys.stderr)
    for item in bad:
        print('  ' + item, file=sys.stderr)
    sys.exit(7)
PY
}

refresh_manifests() {
  python - "$1" <<'PY'
from pathlib import Path
import hashlib, sys
root = Path(sys.argv[1]).resolve()
exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}
files = []
for p in root.rglob('*'):
    if not p.is_file() or any(part in exclude_dirs for part in p.relative_to(root).parts):
        continue
    rel = p.relative_to(root).as_posix()
    if rel in {'PROJECT_FILES.txt', 'checksums.sha256'}:
        continue
    files.append((rel, p))
files.sort(key=lambda x: x[0])
manifest = ['MEGA CHECKER ULTIMATE 10.1.1 — PROJECT FILE MANIFEST', '']
for rel, path in files:
    manifest.append(f'{rel:<84} {path.stat().st_size:>12} bytes')
(root / 'PROJECT_FILES.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')
# Checksum list includes PROJECT_FILES.txt and all source files, but not itself.
checksum_files = sorted(
    [p for p in root.rglob('*') if p.is_file()
     and p.relative_to(root).as_posix() != 'checksums.sha256'
     and not any(part in exclude_dirs for part in p.relative_to(root).parts)],
    key=lambda p: p.relative_to(root).as_posix(),
)
lines = []
for path in checksum_files:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    lines.append(f'{digest}  ./{path.relative_to(root).as_posix()}')
(root / 'checksums.sha256').write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY
}

# If this directory is already a clone, publish from it. Otherwise, clone the
# known repository, overlay only safe project files, then attach the Git metadata
# after a successful push. This preserves the existing GitHub history.
if [[ -d "$SOURCE_ROOT/.git" ]]; then
  WORK="$SOURCE_ROOT"
  ORIGIN="$(git -C "$WORK" remote get-url origin 2>/dev/null)" \
    || die "Thư mục Git hiện tại chưa có remote origin. Đã dừng để tránh push nhầm."
  NORMALIZED="${ORIGIN%.git}"
  case "$NORMALIZED" in
    "https://github.com/${TARGET_REPO}"|"http://github.com/${TARGET_REPO}"|"git@github.com:${TARGET_REPO}"|"ssh://git@github.com/${TARGET_REPO}") ;;
    *) die "Remote hiện tại không phải $TARGET_REPO: $ORIGIN" ;;
  esac
  CURRENT_BRANCH="$(git -C "$WORK" branch --show-current)"
  [[ "$CURRENT_BRANCH" == "$BRANCH" ]] || die "Đang ở nhánh '$CURRENT_BRANCH', trong khi GitHub dùng '$BRANCH'. Không tự đổi nhánh."
  git -C "$WORK" fetch origin "$BRANCH"
  if git -C "$WORK" rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
    git -C "$WORK" merge-base --is-ancestor "origin/$BRANCH" HEAD \
      || die "Nhánh local chưa dựa trên lịch sử GitHub mới nhất. Đã dừng, không rebase/force-push tự động."
  fi
  configure_git_identity
  refresh_manifests "$WORK"
  git -C "$WORK" add -A
  check_staged_paths
  if ! git -C "$WORK" diff --cached --quiet; then
    git -C "$WORK" commit -m "Update MEGA CHECKER ULTIMATE dual-access source"
  fi
  git -C "$WORK" push -u origin "$BRANCH"
else
  TMP_ROOT="$(mktemp -d "${TMPDIR:-$HOME}/mega-checker-publish.XXXXXX")"
  cleanup() { rm -rf "$TMP_ROOT"; }
  trap cleanup EXIT
  WORK="$TMP_ROOT/repo"
  say "Thư mục hiện tại chưa có .git. Đang clone đúng repository hiện hữu để giữ lịch sử..."
  gh repo clone "$TARGET_REPO" "$WORK" -- --single-branch --branch "$BRANCH"

  python - "$SOURCE_ROOT" "$WORK" <<'PY'
from pathlib import Path
import fnmatch, shutil, sys
src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
skip_dirs = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
             '.venv', 'venv', 'backups', 'logs', 'cache', 'tmp', 'output'}
skip_names = {'.env', 'emails.txt', 'email_list.txt', 'combos.txt', 'accounts.txt',
              'credentials.txt', 'passwords.txt', 'secrets.txt', 'cookies.txt', 'tokens.txt'}
skip_patterns = ('*.db', '*.db-wal', '*.db-shm', '*.sqlite', '*.sqlite3', '*.log',
                 '*.tmp', '*.eml', '*.csv', 'dataset_*', 'random_combo_*', 'combo_*',
                 'accounts*', 'credentials*', 'passwords*', 'secrets*', 'cookies*', 'tokens*',
                 'mega_cache*', 'mega_results*', 'root_report*', 'audit_*.json',
                 '.env.*', '*.p12', '*.pfx', '*.key')
for base, dirs, files in __import__('os').walk(src):
    rel_dir = Path(base).relative_to(src)
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for name in files:
        if name in skip_names or any(fnmatch.fnmatch(name, pat) for pat in skip_patterns):
            continue
        rel = (rel_dir / name)
        parts = [x.lower() for x in rel.parts]
        if name.lower().endswith('.pem') and not (parts[:2] == ['tests', 'fixtures'] and name.lower().startswith('dkim_test_')):
            continue
        source = src / rel
        if source.is_symlink() or not source.is_file():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
PY
  # Rebuild the inventories and confirm the staged tree has no local datasets/secrets.
  configure_git_identity
  refresh_manifests "$WORK"
  git -C "$WORK" add -A
  check_staged_paths
  if ! git -C "$WORK" diff --cached --quiet; then
    git -C "$WORK" commit -m "Update MEGA CHECKER ULTIMATE dual-access source"
  fi
  git -C "$WORK" push -u origin "$BRANCH"
  # Copy regenerated inventories back, then attach the already-pushed Git metadata.
  cp -f "$WORK/PROJECT_FILES.txt" "$SOURCE_ROOT/PROJECT_FILES.txt"
  cp -f "$WORK/checksums.sha256" "$SOURCE_ROOT/checksums.sha256"
  cp -a "$WORK/.git" "$SOURCE_ROOT/.git"
  WORK="$SOURCE_ROOT"
  trap - EXIT
  cleanup
fi

say "[SUCCESS] Đã đồng bộ lên repository hiện hữu: $REPO_URL"
say "Branch: $BRANCH"
say "Không tạo repository mới; không force-push."
say "GitHub Actions sẽ chạy workflow QA sau push."
