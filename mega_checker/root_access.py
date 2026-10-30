"""Narrow, read-only Android ROOT bridge for Termux.

Only fixed diagnostics and one explicitly selected file read are exposed.
No arbitrary shell execution, recursive app-data scraping, or system mutation.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator


class RootAccessError(RuntimeError):
    """Root permission is unavailable or a whitelisted operation failed."""


def _su_path() -> str | None:
    found = shutil.which("su")
    if found:
        return found
    for candidate in ("/system/bin/su", "/system/xbin/su", "/sbin/su"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


# Constant and read-only. Never interpolate user input into this script.
_ROOT_DIAGNOSTIC_SCRIPT = r'''
uid="$(id -u 2>/dev/null)"
printf 'UID=%s\n' "$uid"
printf 'SELINUX=%s\n' "$(getenforce 2>/dev/null || echo unknown)"
printf 'ANDROID_RELEASE=%s\n' "$(getprop ro.build.version.release 2>/dev/null)"
printf 'ANDROID_SDK=%s\n' "$(getprop ro.build.version.sdk 2>/dev/null)"
printf 'MANUFACTURER=%s\n' "$(getprop ro.product.manufacturer 2>/dev/null)"
printf 'MODEL=%s\n' "$(getprop ro.product.model 2>/dev/null)"
printf 'KERNEL=%s\n' "$(uname -r 2>/dev/null)"
printf 'CPU_ONLINE=%s\n' "$(cat /sys/devices/system/cpu/online 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null)"
awk '$1=="MemTotal:" {print "MEM_TOTAL_KB=" $2} $1=="MemAvailable:" {print "MEM_AVAILABLE_KB=" $2}' /proc/meminfo 2>/dev/null
if [ -e /data/adb/magisk ] || [ -e /sbin/.magisk ] || [ -e /debug_ramdisk/.magisk ]; then
  printf 'ROOT_MANAGER=Magisk\n'
elif [ -e /data/adb/ksu ]; then
  printf 'ROOT_MANAGER=KernelSU\n'
elif [ -e /data/adb/ap ]; then
  printf 'ROOT_MANAGER=APatch\n'
else
  printf 'ROOT_MANAGER=unknown\n'
fi
i=0
for f in /sys/class/thermal/thermal_zone*/temp; do
  [ -r "$f" ] || continue
  read -r value < "$f" || continue
  case "$value" in ''|*[!0-9-]*) continue ;; esac
  printf 'THERMAL_RAW=%s\n' "$value"
  i=$((i+1))
  [ "$i" -ge 8 ] && break
done
'''


def _run_su(script: str, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    su = _su_path()
    if not su:
        raise RootAccessError("Không tìm thấy su trong Termux/PATH.")
    try:
        proc = subprocess.run(
            [su, "-c", script], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RootAccessError(
            "Hết thời gian chờ quyền ROOT; hãy cấp quyền cho Termux trong root manager."
        ) from exc
    except OSError as exc:
        raise RootAccessError(f"Không chạy được su: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise RootAccessError((proc.stderr or proc.stdout or "su từ chối quyền").strip()[:400])
    return proc


def _read_unprivileged_command(args: list[str], timeout: float = 1.0) -> str:
    """Run a fixed, unprivileged Android information command; failure is non-fatal."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _local_device_facts() -> dict:
    """Collect facts visible to the ordinary Termux UID (no su required)."""
    facts = {
        "uid": str(os.getuid()) if hasattr(os, "getuid") else None,
        "selinux": _read_unprivileged_command(["getenforce"] ) or "unknown",
        "android_release": _read_unprivileged_command(["getprop", "ro.build.version.release"]) or "unknown",
        "android_sdk": _read_unprivileged_command(["getprop", "ro.build.version.sdk"]) or "unknown",
        "manufacturer": _read_unprivileged_command(["getprop", "ro.product.manufacturer"]) or "unknown",
        "model": _read_unprivileged_command(["getprop", "ro.product.model"]) or "unknown",
        "kernel": "unknown",
        "cpu_online": str(os.cpu_count() or "unknown"),
        "memory_total_kb": None,
        "memory_available_kb": None,
        "root_manager": "unknown",
        "thermal_raw": [],
    }
    try:
        import platform
        facts["kernel"] = platform.release() or "unknown"
    except Exception:
        pass
    try:
        with open("/proc/meminfo", "r", encoding="ascii", errors="ignore") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) >= 2 and fields[0] == "MemTotal:":
                    facts["memory_total_kb"] = int(fields[1])
                elif len(fields) >= 2 and fields[0] == "MemAvailable:":
                    facts["memory_available_kb"] = int(fields[1])
    except (OSError, ValueError):
        pass
    # These checks reveal only known marker paths; they do not read app data.
    markers = (
        ("Magisk", ("/data/adb/magisk", "/sbin/.magisk", "/debug_ramdisk/.magisk")),
        ("KernelSU", ("/data/adb/ksu",)),
        ("APatch", ("/data/adb/ap",)),
    )
    for name, paths in markers:
        if any(os.path.exists(item) for item in paths):
            facts["root_manager"] = name
            break
    for thermal_path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            value = thermal_path.read_text(encoding="ascii").strip()
            if value and value.lstrip("-").isdigit():
                facts["thermal_raw"].append(value)
            if len(facts["thermal_raw"]) >= 8:
                break
        except OSError:
            continue
    return facts


def root_status() -> dict:
    """Report device facts in No-Root mode, then attempt optional ROOT escalation."""
    su = _su_path()
    local = _local_device_facts()
    report = {
        "schema": "mega-checker-device-access-v2",
        "access_mode": "root" if local.get("uid") == "0" else "noroot",
        "su_available": bool(su),
        "root_granted": local.get("uid") == "0",
        **local,
        "operations": "read_only",
        "notes": [
            "No-Root là chế độ nền: chỉ đọc thông tin mà UID Termux hiện tại được phép thấy.",
            "ROOT là tùy chọn; chỉ dùng để bổ sung quyền đọc khi người dùng chủ động cho phép.",
            "Không đọc app data riêng tư, không thu thập serial/IMEI/tài khoản.",
            "Không sửa governor, SELinux, kernel, module hoặc phân vùng.",
        ],
    }
    if not su:
        if report["root_granted"]:
            report["access_mode"] = "root"
        else:
            report["root_error"] = "su_not_found_no_root_mode_active"
        return report

    try:
        proc = _run_su(_ROOT_DIAGNOSTIC_SCRIPT)
    except RootAccessError as exc:
        # A missing grant, cancelled prompt or incompatible su must not disable No-Root.
        report["root_error"] = str(exc)[:300]
        report["root_granted"] = False
        return report

    parsed: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed.setdefault(key, []).append(value.strip())

    uid = (parsed.get("UID") or [""])[0]
    report["uid"] = uid or report.get("uid")
    report["root_granted"] = uid == "0"
    report["access_mode"] = "root" if report["root_granted"] else "noroot"
    mapping = (
        ("SELINUX", "selinux"), ("ANDROID_RELEASE", "android_release"),
        ("ANDROID_SDK", "android_sdk"), ("MANUFACTURER", "manufacturer"),
        ("MODEL", "model"), ("KERNEL", "kernel"), ("CPU_ONLINE", "cpu_online"),
        ("ROOT_MANAGER", "root_manager"),
    )
    for key, target in mapping:
        value = (parsed.get(key) or [""])[0]
        if value:
            report[target] = value
    for key, target in (("MEM_TOTAL_KB", "memory_total_kb"),
                        ("MEM_AVAILABLE_KB", "memory_available_kb")):
        value = (parsed.get(key) or [""])[0]
        try:
            report[target] = int(value) if value else report[target]
        except (ValueError, TypeError):
            pass
    if parsed.get("THERMAL_RAW"):
        report["thermal_raw"] = parsed["THERMAL_RAW"][:8]
    if not report["root_granted"]:
        report["root_error"] = "su_did_not_return_uid_0"
    return report


@contextmanager
def open_root_file(path: str | Path) -> Iterator[BinaryIO]:
    """Stream exactly one explicitly chosen absolute file through su/cat."""
    su = _su_path()
    if not su:
        raise RootAccessError("Không tìm thấy su; không thể đọc tệp bằng ROOT.")
    raw_path = str(Path(path).expanduser())
    if not raw_path.startswith("/") or "\x00" in raw_path:
        raise RootAccessError("--root-input yêu cầu một đường dẫn tuyệt đối hợp lệ.")
    command = '[ "$(id -u)" = 0 ] || exit 77; exec cat -- ' + shlex.quote(raw_path)
    try:
        proc = subprocess.Popen(
            [su, "-c", command], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise RootAccessError(f"Không khởi chạy được su: {type(exc).__name__}") from exc
    assert proc.stdout is not None
    try:
        yield proc.stdout
    finally:
        try:
            proc.stdout.close()
        except OSError:
            pass
        try:
            stderr = proc.stderr.read(4096) if proc.stderr else b""
        except OSError:
            stderr = b""
        try:
            returncode = proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise RootAccessError("ROOT cat không kết thúc trong 15 giây.")
        if returncode != 0:
            detail = stderr.decode("utf-8", "replace").strip() or "ROOT không đọc được tệp đã chọn."
            raise RootAccessError(detail[:400])



@contextmanager
def open_dataset_input(path: str | Path, access_mode: str = "auto") -> Iterator[tuple[BinaryIO, str]]:
    """Open a dataset with No-Root-first semantics and optional ROOT fallback.

    auto: ordinary Termux file access first; fall back to su only on PermissionError.
    noroot: never call su.
    root: explicitly stream the selected absolute path through su.
    """
    if access_mode not in {"auto", "noroot", "root"}:
        raise ValueError("access_mode phải là auto, noroot hoặc root")
    source = Path(path).expanduser()
    if access_mode == "root":
        with open_root_file(source) as stream:
            yield stream, "root"
        return

    try:
        stream = source.open("rb")
    except PermissionError as no_root_error:
        if access_mode == "noroot":
            raise
        try:
            with open_root_file(source) as root_stream:
                yield root_stream, "root"
            return
        except RootAccessError as root_error:
            raise RootAccessError(
                f"No-Root không đọc được tệp ({no_root_error}); ROOT fallback không khả dụng ({root_error})."
            ) from root_error
    with stream:
        yield stream, "noroot"

def write_root_report(report: dict, output: str | Path) -> Path:
    target = Path(output).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target
