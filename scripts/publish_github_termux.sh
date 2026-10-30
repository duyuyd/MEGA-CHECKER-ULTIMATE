#!/data/data/com.termux/files/usr/bin/bash
set -Eeuo pipefail

# Publish the current MEGA CHECKER project to a NEW GitHub repository.
# The default visibility is PRIVATE. Nothing is pushed to an existing unrelated repo.

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_NAME="MEGA-CHECKER-ULTIMATE"
cd "$PROJECT_ROOT"

printf '\n===============================================\n'
printf '  MEGA CHECKER ULTIMATE — GITHUB PUBLISHER\n'
printf '===============================================\n\n'

if ! command -v pkg >/dev/null 2>&1; then
  echo '[ERROR] Script này được thiết kế cho Termux trên Android.' >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1 || ! command -v gh >/dev/null 2>&1; then
  echo '[INFO] Đang cài Git và GitHub CLI...'
  pkg update -y
  pkg install -y git gh
fi

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  echo
  echo '[LOGIN] GitHub sẽ hiển thị mã xác nhận / mở trình duyệt.'
  echo 'Hãy đăng nhập đúng tài khoản GitHub của bạn và chấp thuận GitHub CLI.'
  gh auth login --hostname github.com --git-protocol https --web --skip-ssh-key
fi

gh auth status --hostname github.com >/dev/null
gh auth setup-git --hostname github.com
LOGIN="$(gh api user --jq '.login')"
USER_ID="$(gh api user --jq '.id')"
if [[ -z "$LOGIN" || -z "$USER_ID" ]]; then
  echo '[ERROR] Không lấy được tài khoản GitHub đã đăng nhập.' >&2
  exit 3
fi

# Prevent accidental publishing of local databases and secrets.
# Runtime logs are excluded by .gitignore and are not treated as source files.
PRIVATE_FILES="$(find . -maxdepth 4 -type f \
  \( -name '*.db' -o -name '*.db-wal' -o -name '*.db-shm' \
     -o -name '.env' -o -name '.env.*' \) -print -quit)"
if [[ -n "$PRIVATE_FILES" ]]; then
  echo '[ERROR] Phát hiện database hoặc file môi trường có thể chứa dữ liệu riêng tư.' >&2
  echo 'Hãy di chuyển dữ liệu riêng tư ra ngoài trước khi đưa mã nguồn lên GitHub.' >&2
  echo "$PRIVATE_FILES"
  exit 4
fi

if [[ ! -d .git ]]; then
  git init -b main
fi

# Use GitHub's noreply identity; no personal email is written into commits.
git config user.name "$LOGIN"
git config user.email "${USER_ID}+${LOGIN}@users.noreply.github.com"

git add -A
if ! git diff --cached --quiet; then
  git commit -m "MEGA CHECKER ULTIMATE 9.0 initial release"
fi

if git remote get-url origin >/dev/null 2>&1; then
  ORIGIN="$(git remote get-url origin)"
  case "$ORIGIN" in
    "https://github.com/${LOGIN}/${REPO_NAME}.git"|"git@github.com:${LOGIN}/${REPO_NAME}.git") ;;
    *)
      echo "[ERROR] Origin hiện tại trỏ tới repository khác: $ORIGIN" >&2
      echo 'Đã dừng để không đẩy nhầm dự án.' >&2
      exit 5
      ;;
  esac
  git push -u origin HEAD
else
  if gh repo view "${LOGIN}/${REPO_NAME}" >/dev/null 2>&1; then
    echo "[INFO] Repository ${LOGIN}/${REPO_NAME} đã tồn tại; sẽ dùng repository này."
    git remote add origin "https://github.com/${LOGIN}/${REPO_NAME}.git"
    git push -u origin HEAD
  else
    echo
    echo 'Mặc định tạo repository PRIVATE để bảo vệ source và dữ liệu cấu hình.'
    read -r -p 'Nhấn Enter để tạo PRIVATE, hoặc gõ PUBLIC để công khai mã nguồn: ' VISIBILITY
    if [[ "${VISIBILITY^^}" == "PUBLIC" ]]; then
      gh repo create "$REPO_NAME" --public --description "MEGA CHECKER ULTIMATE — privacy-first email and domain diagnostics" --source . --remote origin --push
    else
      gh repo create "$REPO_NAME" --private --description "MEGA CHECKER ULTIMATE — privacy-first email and domain diagnostics" --source . --remote origin --push
    fi
  fi
fi

URL="$(gh repo view "${LOGIN}/${REPO_NAME}" --json url --jq '.url')"
printf '\n[SUCCESS] Đã đẩy mã nguồn lên GitHub.\n'
printf 'Repository: %s\n' "$URL"
printf 'Nhánh: %s\n' "$(git branch --show-current)"
printf 'GitHub Actions sẽ tự chạy bộ kiểm thử sau push.\n'
printf '\nLưu ý: không tải lên database/email thật hoặc API key.\n'
