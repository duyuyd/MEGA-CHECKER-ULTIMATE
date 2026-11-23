"""Exercise the signed APK through Android's native UI with public QA inputs."""
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PACKAGE = "vn.megachecker.android"


def adb(*args, timeout=25):
    return subprocess.check_output(["adb", *args], text=True, timeout=timeout)


def hierarchy():
    adb("shell", "uiautomator", "dump", "/sdcard/mega-ci.xml", timeout=10)
    return ET.fromstring(adb("exec-out", "cat", "/sdcard/mega-ci.xml"))


def find(view, predicate=lambda node: True, timeout=35):
    deadline = time.monotonic() + timeout
    visible = []
    while time.monotonic() < deadline:
        try:
            document = hierarchy()
            visible = [n.get("resource-id") for n in document.iter("node") if n.get("resource-id")]
            for node in document.iter("node"):
                if node.get("resource-id") == f"{PACKAGE}:id/{view}" and predicate(node):
                    return node
        except (subprocess.SubprocessError, ET.ParseError):
            pass
        time.sleep(0.2)
    window = adb("shell", "dumpsys", "window")
    focus = [line.strip() for line in window.splitlines() if "mCurrentFocus=" in line]
    raise AssertionError(f"Missing Android state for {view!r}. Focus {focus}. Views {visible[:20]}")


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
    adb("shell", "svc", "power", "stayon", "true")
    adb("shell", "settings", "put", "system", "screen_off_timeout", "1800000")
    adb("shell", "wm", "dismiss-keyguard")
    adb("shell", "am", "start", "-W", "-a", "android.intent.action.MAIN",
        "-c", "android.intent.category.LAUNCHER", "-n", f"{PACKAGE}/.MainActivity")
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
    tap("run_online")
    dns = result_contains("DNS cho mailinator.com")
    assert all(label in dns for label in ("MX:", "SPF:", "DMARC:", "Nguồn DNS:"))
    print("DNS on the emulator: " + dns, flush=True)

    tap("tab_password")
    enter("password")
    tap("run_online")
    report = result_contains("Đã có trong dữ liệu rò rỉ", "Chưa xác định được kết quả")
    print("Pwned Passwords on the emulator: " + report, flush=True)
    pid = adb("shell", "pidof", PACKAGE).strip()
    # Open a full-screen system activity and return to the same activity with Back.
    # Wait until Settings visibly owns the screen before triggering the return.
    adb("shell", "am", "start", "-W", "-a", "android.settings.SETTINGS")
    deadline = time.monotonic() + 20
    while not any(n.get("package") == "com.android.settings" for n in hierarchy().iter("node")):
        if time.monotonic() >= deadline:
            raise AssertionError("The system Settings screen did not enter the foreground")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    find("run_local", lambda n: n.get("enabled") == "false")
    assert adb("shell", "pidof", PACKAGE).strip() == pid
    assert find("field").get("password") == "true"
    print("PASS: backgrounding cleared the private entry", flush=True)


if __name__ == "__main__":
    main()
