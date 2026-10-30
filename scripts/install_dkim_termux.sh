#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "${1:-}" in
  "") PACKAGE="dkimpy==1.1.8" ;;
  --ed25519) PACKAGE="dkimpy[ed25519]==1.1.8" ;;
  *) echo "Dùng: bash scripts/install_dkim_termux.sh [--ed25519]" >&2; exit 2 ;;
esac

source "$ROOT/scripts/termux_python_pip.sh"
ensure_python_pip

python -m pip install --disable-pip-version-check --no-input --upgrade "$PACKAGE"
python - <<'PY'
import dkim
print("DKIM verifier:", getattr(dkim, "__version__", "dkimpy installed"))
if not hasattr(dkim, "DKIM"):
    raise SystemExit("Không tìm thấy API DKIM.verify trong gói đã cài")
print("DKIM cryptographic API: OK")
PY
python mega_checker.py self-test
python -m unittest discover -s tests -v
printf '\nĐã cài bộ xác minh DKIM. Lệnh xác minh:\n'
printf 'python mega_checker.py dkim --verify --headers-file ~/storage/downloads/original.eml\n'
printf '\nNếu cần Ed25519, chạy lại script với --ed25519.\n'
