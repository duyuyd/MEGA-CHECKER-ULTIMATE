#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
tool_dir="$(find "$ANDROID_HOME/build-tools" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n 1)"
source_apk="android/app/build/outputs/apk/release/app-release-unsigned.apk"
mkdir -p dist
output="dist/MEGA-Checker-Android.apk"
if [[ -n "${APK_KEYSTORE_B64:-}${APK_STORE_PASSWORD:-}${APK_KEY_PASSWORD:-}${APK_KEY_ALIAS:-}" ]]; then
  : "${APK_KEYSTORE_B64:?missing keystore}" "${APK_STORE_PASSWORD:?missing store password}" "${APK_KEY_ALIAS:?missing alias}"
  export APK_KEY_PASSWORD="${APK_KEY_PASSWORD:-$APK_STORE_PASSWORD}"
  printf '%s' "$APK_KEYSTORE_B64" | base64 --decode > "$work/signing.p12"
  signing_note="Đã ký bằng khóa phát hành của kho GitHub."
else
  export APK_STORE_PASSWORD="$(openssl rand -hex 32)"
  export APK_KEY_PASSWORD="$APK_STORE_PASSWORD"
  APK_KEY_ALIAS=megachecker
  keytool -genkeypair -noprompt -keystore "$work/signing.p12" -storetype PKCS12 \
    -storepass:env APK_STORE_PASSWORD -keypass:env APK_KEY_PASSWORD -alias "$APK_KEY_ALIAS" \
    -keyalg RSA -keysize 3072 -validity 10000 -dname "CN=MEGA Checker Android"
  signing_note="APK này dùng khóa riêng của lần build. Khi chuyển sang bản có chữ ký khác, Android yêu cầu gỡ bản cũ trước."
fi
echo "Aligning the unsigned APK for 16 KiB native library pages"
"$tool_dir/zipalign" -P 16 -f 4 "$source_apk" "$work/aligned.apk"
echo "Signing the aligned release APK"
"$tool_dir/apksigner" sign --ks "$work/signing.p12" --ks-key-alias "$APK_KEY_ALIAS" \
  --ks-pass env:APK_STORE_PASSWORD --key-pass env:APK_KEY_PASSWORD --out "$output" "$work/aligned.apk"
echo "Verifying signature and extracting the public certificate fingerprint"
"$tool_dir/apksigner" verify --verbose --print-certs "$output" | tee "$work/certificate.txt"
certificate="$(awk '/certificate SHA-256 digest:/ {print $NF; exit}' "$work/certificate.txt")"
[[ "$certificate" =~ ^[[:xdigit:]]{64}$ ]] || { echo "Missing signer SHA-256 in verification output" >&2; exit 1; }
"$tool_dir/zipalign" -c -P 16 4 "$output"
# v4 sidecar files are only used for incremental installation over ADB.
rm -f -- "$output.idsig"
(cd dist && sha256sum MEGA-Checker-Android.apk > SHA256SUMS.txt)
printf '%s\n\n%s\n\n%s\n' "APK Android 7+ (arm64-v8a, x86_64). Commit $GITHUB_SHA." \
  "$signing_note" "SHA-256 của chứng thư Android: $certificate" > dist/release-notes.txt
cat dist/SHA256SUMS.txt
