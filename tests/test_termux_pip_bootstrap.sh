#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"

cat > "$TMP/bin/python" <<'PY'
#!/usr/bin/env bash
if [[ "${1:-}" == "-m" && "${2:-}" == "pip" && "${3:-}" == "--version" ]]; then
  if [[ "${PIP_ALREADY:-0}" == "1" || -f "${PIP_MARKER:-/nonexistent}" ]]; then
    echo "pip test-stub"
    exit 0
  fi
  exit 1
fi
exit 0
PY
cat > "$TMP/bin/pkg" <<'PKG'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "${PKG_LOG}"
if [[ "${1:-}" == "install" && "${*: -1}" == "python-pip" ]]; then
  touch "${PIP_MARKER}"
  exit 0
fi
if [[ "${1:-}" == "update" ]]; then exit 0; fi
exit 2
PKG
chmod +x "$TMP/bin/python" "$TMP/bin/pkg"

: > "$TMP/pkg1.log"
PATH="$TMP/bin:$PATH" PIP_ALREADY=1 PIP_MARKER="$TMP/marker1" PKG_LOG="$TMP/pkg1.log" \
  bash -c 'source "$1"; ensure_python_pip' _ "$ROOT/scripts/termux_python_pip.sh" >/dev/null
[[ ! -s "$TMP/pkg1.log" ]]

: > "$TMP/pkg2.log"
PATH="$TMP/bin:$PATH" PIP_ALREADY=0 PIP_MARKER="$TMP/marker2" PKG_LOG="$TMP/pkg2.log" \
  bash -c 'source "$1"; ensure_python_pip' _ "$ROOT/scripts/termux_python_pip.sh" >/dev/null
[[ -f "$TMP/marker2" ]]
grep -q 'install -y python-pip' "$TMP/pkg2.log"

echo "[PASS] Existing pip is preserved"
echo "[PASS] Missing pip triggers Termux python-pip install"
echo "TERMUX PIP BOOTSTRAP TEST: 2/2"
