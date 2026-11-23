"""Exercise the signed APK through Android's native UI with public QA inputs."""
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PACKAGE = "vn.megachecker.android"


def adb(*args, timeout=25):
    return subprocess.check_output(["adb", *args], text=True, timeout=timeout)


def find(view, predicate=lambda node: True, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            adb("shell", "uiautomator", "dump", "/sdcard/mega-ci.xml", timeout=10)
            document = ET.fromstring(adb("exec-out", "cat", "/sdcard/mega-ci.xml"))
            for node in document.iter("node"):
                if node.get("resource-id") == f"{PACKAGE}:id/{view}" and predicate(node):
                    return node
        except (subprocess.SubprocessError, ET.ParseError):
            pass
        time.sleep(0.2)
    raise AssertionError(f"Android view {view!r} did not reach the expected state")


def tap(view):
    node = find(view, lambda n: n.get("enabled") == "true")
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))


def enter(value):
    tap("field")
    adb("shell", "input", "text", value)
    ime = adb("shell", "dumpsys", "input_method")
    if "mInputShown=true" in ime or "mIsInputViewShown=true" in ime:
        adb("shell", "input", "keyevent", "KEYCODE_BACK")


def result_contains(*parts):
    return find("result", lambda n: any(p in n.get("text", "") for p in parts)).get("text", "")


def main():
    apk = sys.argv[1]
    adb("install", "-r", apk, timeout=120)
    adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")
    field = find("field")
    assert field.get("password") == "true"
    assert find("run_local").get("enabled") == "false"
    enter("abababab")
    tap("run_local")
    report = result_contains("lặp lại cùng một cụm")
    assert "8 ký tự · 2 ký tự khác nhau" in report and "Thời gian phân tích trên máy" in report
    assert "abababab" not in report
    print("PASS: installed release APK and assessed a typed, masked password", flush=True)

    tap("tab_email")
    assert not find("field").get("text", "").endswith("abababab")
    enter("tester@mailinator.com")
    tap("run_local")
    report = result_contains("Cấu trúc email hợp lệ")
    assert "Tên miền đăng ký: mailinator.com" in report and "email tạm" in report
    print("PASS: packaged suffix and disposable-domain data were read on Android", flush=True)

    tap("tab_password")
    enter("password")
    tap("run_online")
    report = result_contains("Đã có trong dữ liệu rò rỉ", "Chưa xác định được kết quả")
    print("Pwned Passwords on the emulator: " + report, flush=True)
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")
    assert find("run_local").get("enabled") == "false"
    print("PASS: backgrounding cleared the private entry", flush=True)


if __name__ == "__main__":
    main()
