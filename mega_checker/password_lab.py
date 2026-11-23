"""Offline arithmetic for comparing password lengths and alphabets."""
from __future__ import annotations

import getpass
import re
import string
import sys
import warnings
from time import perf_counter_ns
from decimal import Decimal


DEFAULT_RATE = 1_000_000
MAX_LENGTH = 256
MAX_ALPHABET = 0x110000  # Number of Unicode code points.
VIDEO_GROUPS = (
    string.ascii_lowercase, string.ascii_uppercase, string.digits, "!§$%&/()=?-_",
)


def combination_counts(length: int, alphabet_size: int) -> tuple[int, int]:
    """Count strings of exactly this length, then of all lengths from 1 to it."""
    if not 1 <= length <= MAX_LENGTH:
        raise ValueError(f"Độ dài phải từ 1 đến {MAX_LENGTH} ký tự.")
    if not 1 <= alphabet_size <= MAX_ALPHABET:
        raise ValueError(f"Cỡ bảng ký tự phải từ 1 đến {MAX_ALPHABET}.")
    exact = alphabet_size ** length
    if alphabet_size == 1:
        return exact, length
    return exact, alphabet_size * (exact - 1) // (alphabet_size - 1)


def _video_alphabet_size(symbols: set[str]) -> int | None:
    if symbols.difference(*VIDEO_GROUPS):
        return None
    return sum(len(group) for group in VIDEO_GROUPS if not symbols.isdisjoint(group))


def _read_private_password() -> str:
    if not sys.stdin.isatty():
        raise ValueError("Hãy mở terminal để nhập ẩn hoặc dùng --length và --alphabet-size.")
    with warnings.catch_warnings():
        # getpass can fall back to visible input when the terminal cannot hide it.
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass("Nhập ẩn mật khẩu rồi bấm Enter: ")
        except getpass.GetPassWarning:
            raise ValueError("Terminal này không hỗ trợ nhập ẩn. Hãy dùng --length và --alphabet-size.") from None


def _whole(number: int) -> str:
    # Group ordinary counts for a phone screen. Keep very large counts readable.
    if number >= 10 ** 30:
        return f"≈ {Decimal(number):.3E}".replace(".", ",")
    return f"{number:,}".replace(",", ".")


def _duration(count: int, rate: int) -> str:
    seconds = Decimal(count) / Decimal(rate)
    for unit, factor in (("năm", 31_536_000), ("ngày", 86_400), ("giờ", 3600),
                         ("phút", 60), ("giây", 1), ("ms", Decimal("0.001"))):
        if seconds >= factor:
            value = seconds / factor
            shown = f"{value:.3E}" if value >= 1_000_000_000 else f"{value:,.2f}"
            return f"{shown.translate(str.maketrans(',.', '.,'))} {unit}"
    return "< 1 ms"


def _show_case(label: str, length: int, alphabet: int, rate: int) -> int:
    exact, total = combination_counts(length, alphabet)
    print(f"\n{label} · {length} ký tự · bảng {_whole(alphabet)} ký tự")
    print(f"  Đúng độ dài {length}       {_whole(exact)} chuỗi")
    print(f"  Từ 1 đến {length} ký tự    {_whole(total)} chuỗi")
    print(f"  Thời gian xét hết   ≈ {_duration(total, rate)}")
    return total


def password_report(value: str, alphabet_size: int | None = None, rate: int = DEFAULT_RATE) -> str:
    """Return observations about this input. The raw input never enters the report."""
    started = perf_counter_ns()
    length = len(value)
    if not 1 <= length <= MAX_LENGTH:
        raise ValueError(f"Mật khẩu cần có từ 1 đến {MAX_LENGTH} ký tự.")
    if rate < 1:
        raise ValueError("Tốc độ giả định phải là số nguyên dương.")
    symbols = set(value)
    findings = []
    if length < 15:
        findings.append("Dưới 15 ký tự nếu dùng làm yếu tố đăng nhập duy nhất.")
    folded = value.casefold()
    if value.isspace():
        findings.append("Toàn bộ chuỗi là khoảng trắng.")
    elif length > 1 and (folded + folded).find(folded, 1, -1) >= 0:
        findings.append("Toàn bộ mật khẩu lặp lại cùng một cụm ký tự.")
    elif re.search(r"(.)\1{3,}", folded, flags=re.DOTALL):
        findings.append("Có ít nhất bốn ký tự giống nhau liền nhau.")
    rows = (string.digits, string.ascii_lowercase, "qwertyuiop", "asdfghjkl", "zxcvbnm")
    if any(folded[i:i + 4] in row or folded[i:i + 4] in row[::-1]
           for i in range(len(folded) - 3) for row in rows):
        findings.append("Có dãy chữ, số hoặc phím liền kề.")
    lines = [f"{length} ký tự · {len(symbols)} ký tự khác nhau"]
    lines.extend("• " + item for item in findings)
    if not findings:
        lines.append("Chưa thấy dấu hiệu ngắn, lặp cụm hoặc dãy liền kề theo các phép kiểm tra cục bộ.")
    if alphabet_size is None:
        alphabet_size = _video_alphabet_size(symbols)
    if alphabet_size is not None:
        if alphabet_size < len(symbols):
            raise ValueError("Cỡ bảng nhỏ hơn số ký tự khác nhau trong mật khẩu.")
        _, total = combination_counts(length, alphabet_size)
        lines.append(f"Giả định bảng {alphabet_size} ký tự: {_whole(total)} chuỗi từ độ dài 1 đến {length}.")
        lines.append(f"Xét hết ở {_whole(rate)} lượt/giây: ≈ {_duration(total, rate)} (ước tính).")
    elapsed = (perf_counter_ns() - started) / 1_000_000
    lines.append(f"Thời gian phân tích trên máy: {elapsed:.3f} ms".replace(".", ","))
    return "\n".join(lines)


def run_password_lab(*, length: int | None = None, alphabet_size: int | None = None,
                     rate: int = DEFAULT_RATE, prompt: bool = False) -> int:
    try:
        if rate < 1:
            raise ValueError("Tốc độ giả định phải là số nguyên dương.")
        if prompt or (length is None and alphabet_size is None):
            print(password_report(_read_private_password(), alphabet_size, rate))
        elif length is not None and alphabet_size is not None:
            _show_case("Bảng ký tự của bạn", length, alphabet_size, rate)
            print(f"  Tốc độ giả định     {_whole(rate)} lượt/giây")
        else:
            raise ValueError("Hãy dùng --length cùng --alphabet-size, hoặc dùng --prompt để nhập ẩn.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except EOFError:
        print("Đã đóng đầu vào.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nĐã hủy.", file=sys.stderr)
        return 130
