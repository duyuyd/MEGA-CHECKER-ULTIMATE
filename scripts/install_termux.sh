#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
pkg update -y
pkg install -y python
python mega_checker.py self-test
echo "Cài đặt hoàn tất. Không cần pip cài thư viện bổ sung."
