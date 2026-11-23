"""Exercise only the isolated no-network Android APK on Android 14."""
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

PACKAGE = "vn.nptduy.localpasswordlab"


def adb(*args, timeout=30):
    return subprocess.check_output(["adb", *args], text=True, timeout=timeout)


def dump():
    adb("shell", "uiautomator", "dump", "/sdcard/npt-password-test.xml", timeout=15)
    return ET.fromstring(adb("exec-out", "cat", "/sdcard/npt-password-test.xml", timeout=15))


def find(resource, predicate=None, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for node in dump().iter("node"):
                if node.get("resource-id") == f"{PACKAGE}:id/{resource}" and (
                    predicate is None or predicate(node)
                ):
                    return node
        except (ET.ParseError, subprocess.SubprocessError):
            pass
        time.sleep(0.25)
    raise AssertionError(f"Unable to locate {resource}")


def tap(resource):
    node = find(resource, lambda item: item.get("enabled") == "true")
    x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
    adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))


def main():
    apk = sys.argv[1]
    adb("install", "-r", apk, timeout=120)
    adb("shell", "wm", "dismiss-keyguard")
    adb("shell", "am", "start", "-W", "-n", f"{PACKAGE}/.MainActivity")
    assert find("sample_input").get("password") == "true"
    assert find("alphabet_input").get("text", "").find("π") >= 0
    tap("benchmark_button")
    value = find("result_text", lambda x: "Đã hoàn thành đo 1.000.000" in x.get("text", ""))
    assert "1.000.000" in value.get("text", "")
    print("PASS: completed genuine one-million local trial benchmark", flush=True)
    tap("sample_input")
    adb("shell", "input", "text", "b")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    tap("compare_button")
    value = find("result_text", lambda x: "TRÙNG KHỚP CHUỖI MẪU" in x.get("text", ""))
    assert "Không phải xác nhận Gmail" in value.get("text", "")
    assert find("sample_input").get("text", "") in ("", None)
    print("PASS: local reference match without exposing plaintext", flush=True)
    adb("shell", "am", "start", "-W", "-a", "android.settings.SETTINGS")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    assert find("sample_input").get("password") == "true"
    assert "Đã xóa kết quả" in find("result_text").get("text", "")
    print("PASS: background clears reference and result", flush=True)


if __name__ == "__main__":
    main()
