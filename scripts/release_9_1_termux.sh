#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "${1:-}" in
  "") DKIM_PACKAGE="dkimpy==1.1.8" ;;
  --ed25519) DKIM_PACKAGE="dkimpy[ed25519]==1.1.8" ;;
  *) echo "Dùng: bash scripts/release_9_1_termux.sh [--ed25519]" >&2; exit 2 ;;
esac

if [ "$(git branch --show-current)" != "main" ]; then
  echo "Dừng: cần ở nhánh main trước khi phát hành." >&2
  exit 2
fi
REMOTE="$(git remote get-url origin)"
case "$REMOTE" in
  *duyuyd/MEGA-CHECKER-ULTIMATE*) ;;
  *) echo "Dừng: origin không phải duyuyd/MEGA-CHECKER-ULTIMATE; giữ nguyên repo." >&2; exit 2 ;;
esac

# Termux splits Python and pip into separate packages.
source "$ROOT/scripts/termux_python_pip.sh"
ensure_python_pip

python -m pip install --disable-pip-version-check --no-input --upgrade "$DKIM_PACKAGE"
python - <<'PY'
import dkim
assert hasattr(dkim, "DKIM"), "dkimpy DKIM API missing"
print("[PASS] dkimpy API available:", getattr(dkim, "__version__", "1.1.8"))
PY
python -m compileall -q mega_checker mega_checker.py
python mega_checker.py --version
python mega_checker.py self-test
python -m unittest discover -s tests -v
python -S -m unittest discover -s tests -q
python scripts/runtime_smoke_test.py
bash tests/test_termux_pip_bootstrap.sh
git diff --check

git add \
  .github/workflows/tests.yml \
  CHANGELOG.md README.md README_VI.md THIRD_PARTY_NOTICES.md \
  PROJECT_FILES.txt checksums.sha256 requirements-dkim.txt \
  mega_checker/__init__.py mega_checker/cli.py mega_checker/dkim.py mega_checker/dnsintel.py \
  scripts/install_dkim_termux.sh scripts/release_9_1_termux.sh scripts/termux_python_pip.sh \
  docs/QA_DKIM_9.1.0.md docs/QA_LAST_RUN.txt docs/TERMUX.md \
  tests/test_dkim_verify.py tests/test_dkimpy_integration.py tests/test_termux_pip_bootstrap.sh tests/fixtures/

git diff --cached --check
if git diff --cached --quiet; then
  echo "Không có thay đổi mới để commit."
else
  git commit -m "Release 9.1.1: fix Termux pip bootstrap"
fi
git push origin main
printf '\n[THÀNH CÔNG] Đã cập nhật 9.1.1 lên GitHub.\n'
printf 'GitHub Actions sẽ chạy lại kiểm thử Python 3.13 và 3.14.\n'
