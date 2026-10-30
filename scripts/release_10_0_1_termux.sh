#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ "$(git branch --show-current)" != "main" ]; then
  echo "Dừng: cần ở nhánh main trước khi phát hành." >&2
  exit 2
fi
REMOTE="$(git remote get-url origin)"
case "$REMOTE" in
  *duyuyd/MEGA-CHECKER-ULTIMATE*) ;;
  *) echo "Dừng: origin không phải duyuyd/MEGA-CHECKER-ULTIMATE; giữ nguyên repo." >&2; exit 2 ;;
esac

source "$ROOT/scripts/termux_python_pip.sh"
ensure_python_pip
python --version
python mega_checker.py --version
python -m compileall -q mega_checker mega_checker.py
python mega_checker.py self-test
python -m unittest discover -s tests -v
python -S -m unittest discover -s tests -q
python scripts/runtime_smoke_test.py
bash tests/test_termux_pip_bootstrap.sh
git diff --check

git add CHANGELOG.md README.md README_VI.md PROJECT_FILES.txt checksums.sha256 \
  mega_checker/__init__.py mega_checker/cli.py mega_checker/dataset_audit.py \
  tests/test_dataset_audit.py docs/QA_LAST_RUN_10.0.1.txt \
  scripts/release_10_0_1_termux.sh

git diff --cached --check
if git diff --cached --quiet; then
  echo "Không có thay đổi mới để commit."
else
  git commit -m "Release 10.0.1: harden dataset audit privacy and boundaries"
fi
git push origin main
printf '\n[THÀNH CÔNG] Đã cập nhật 10.0.1 lên GitHub.\n'
