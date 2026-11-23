"""Offline arithmetic for comparing password lengths and alphabets."""
from __future__ import annotations

import getpass
import string
import sys
import warnings
from decimal import Decimal


DEFAULT_RATE = 1_000_000
MAX_LENGTH = 256
MAX_ALPHABET = 0x110000  # Number of Unicode code points.
VIDEO_GROUPS = (
    string.ascii_lowercase, string.ascii_uppercase, string.digits, "!§$%&/()=?-_",
)
VIDEO_EXAMPLES = ("ac12!", "ABcd12!")


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


def _private_shape(alphabet_size: int | None) -> tuple[int, int]:
    if not sys.stdin.isatty():
        raise ValueError("Hãy mở terminal để nhập ẩn hoặc dùng --length và --alphabet-size.")
    with warnings.catch_warnings():
        # getpass can fall back to visible input when the terminal cannot hide it.
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            sample = getpass.getpass("Nhập ẩn một chuỗi ví dụ rồi bấm Enter: ")
        except getpass.GetPassWarning:
            raise ValueError("Terminal này không hỗ trợ nhập ẩn. Hãy dùng --length và --alphabet-size.") from None
    if not 1 <= len(sample) <= MAX_LENGTH:
        raise ValueError(f"Chuỗi ví dụ cần có từ 1 đến {MAX_LENGTH} ký tự.")
    symbols = set(sample)
    if alphabet_size is None:
        alphabet_size = _video_alphabet_size(symbols)
    if alphabet_size is None:
        print("Ví dụ dùng ký tự ngoài các nhóm trong video.")
        value = input(f"Cỡ bảng ký tự bạn muốn mô hình hóa (ít nhất {len(symbols)}): ").strip()
        if not value.isascii() or not value.isdecimal() or len(value) > len(str(MAX_ALPHABET)):
            raise ValueError("Hãy nhập một số nguyên dương cho cỡ bảng ký tự.")
        alphabet_size = int(value)
    if alphabet_size < len(symbols):
        raise ValueError("Cỡ bảng nhỏ hơn số ký tự khác nhau trong ví dụ.")
    return len(sample), alphabet_size


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


def run_password_lab(*, length: int | None = None, alphabet_size: int | None = None,
                     rate: int = DEFAULT_RATE, prompt: bool = False) -> int:
    """Display either the two video examples or a single custom model."""
    try:
        if rate < 1:
            raise ValueError("Tốc độ giả định phải là số nguyên dương.")
        if prompt:
            length, alphabet_size = _private_shape(alphabet_size)
        if length is None and alphabet_size is None:
            totals = []
            print(f"\nTốc độ giả định   {_whole(rate)} lượt/giây")
            for example in VIDEO_EXAMPLES:
                size = _video_alphabet_size(set(example))
                assert size is not None
                totals.append(_show_case(example, len(example), size, rate))
            ratio = Decimal(totals[1]) / totals[0]
            print(f"\nVí dụ thứ hai có tổng số chuỗi lớn gấp khoảng {_whole(round(ratio))} lần.")
        elif length is not None and alphabet_size is not None:
            _show_case("Ví dụ của bạn", length, alphabet_size, rate)
            print(f"  Tốc độ giả định     {_whole(rate)} lượt/giây")
        else:
            raise ValueError("Hãy dùng --length cùng --alphabet-size, hoặc chọn --prompt để nhập ẩn.")
        print("Thời gian trên tính cho toàn bộ số chuỗi ở tốc độ giả định.")
        if prompt:
            print("Chuỗi do người đặt có thể dễ đoán hơn nhiều so với mô hình này.")
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
