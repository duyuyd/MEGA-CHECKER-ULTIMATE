#!/data/data/com.termux/files/usr/bin/bash
# Shared pip bootstrap for Termux. pip is packaged separately as python-pip.
set -euo pipefail

ensure_python_pip() {
  if python -m pip --version >/dev/null 2>&1; then
    echo "[PASS] Python pip is available: $(python -m pip --version)"
    return 0
  fi

  if ! command -v pkg >/dev/null 2>&1; then
    echo "[ERROR] python -m pip is missing and Termux 'pkg' was not found." >&2
    echo "On Termux, install it with: pkg install python-pip -y" >&2
    return 1
  fi

  echo "[INFO] Termux packages pip separately from Python. Installing python-pip..."
  if ! pkg install -y python-pip; then
    echo "[INFO] Package index may be stale; refreshing Termux package index..."
    pkg update -y
    pkg install -y python-pip
  fi

  if ! python -m pip --version >/dev/null 2>&1; then
    echo "[ERROR] python-pip was installed but this Python still cannot import pip." >&2
    echo "Check: which python; python --version; pkg list-installed | grep -E '^(python|python-pip)/'" >&2
    return 1
  fi
  echo "[PASS] Python pip is now available: $(python -m pip --version)"
}
