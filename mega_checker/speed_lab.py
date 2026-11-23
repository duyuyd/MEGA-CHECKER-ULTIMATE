"""Bounded, offline candidate-generation benchmark for learning about search space.

This module never tests passwords, hashes, services, accounts or credentials.
Its throughput describes a four-character synthetic candidate generator only.
"""
from __future__ import annotations

from itertools import islice, product
import string
from time import perf_counter_ns
import sys

from .password_lab import MAX_ALPHABET, MAX_LENGTH, _duration, _whole, combination_counts

DEFAULT_SAMPLES = 80_000
MAX_SAMPLES = 250_000
BENCHMARK_ALPHABET = string.ascii_letters + string.digits + string.punctuation


def measure_candidate_rate(samples: int = DEFAULT_SAMPLES) -> dict[str, int]:
    """Measure a bounded number of generated strings using a fixed synthetic alphabet.

    Limiting samples avoids the exponential and sometimes endless loop shown in
    simple password-guessing demonstrations. The work does not compare secrets.
    """
    if type(samples) is not int or not 1 <= samples <= MAX_SAMPLES:
        raise ValueError(f"Số mẫu phải từ 1 đến {MAX_SAMPLES:,}.")
    start = perf_counter_ns()
    processed = 0
    for candidate in islice(product(BENCHMARK_ALPHABET, repeat=4), samples):
        "".join(candidate)
        processed += 1
    elapsed_ns = max(1, perf_counter_ns() - start)
    return {
        "samples": processed,
        "elapsed_ns": elapsed_ns,
        "rate_per_second": max(1, processed * 1_000_000_000 // elapsed_ns),
    }


def speed_report(length: int | str, alphabet_size: int = 74,
                 samples: int = DEFAULT_SAMPLES) -> str:
    """Show measured local generation speed and clearly labeled extrapolations."""
    try:
        length = int(length)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Độ dài phải là số nguyên từ 1 đến 256.") from exc
    if not 1 <= length <= MAX_LENGTH:
        raise ValueError(f"Độ dài phải từ 1 đến {MAX_LENGTH}.")
    if type(alphabet_size) is not int or not 1 <= alphabet_size <= MAX_ALPHABET:
        raise ValueError(f"Cỡ bảng phải từ 1 đến {MAX_ALPHABET}.")
    exact, total = combination_counts(length, alphabet_size)
    measured = measure_candidate_rate(samples)
    rate = measured["rate_per_second"]
    duration_ms = measured["elapsed_ns"] / 1_000_000
    return "\n".join((
        f"Độ dài {length} · bảng {alphabet_size} ký tự",
        f"Số chuỗi đúng độ dài: {_whole(exact)}",
        f"Số chuỗi từ 1 đến {length}: {_whole(total)}",
        f"Đo thực tế trên máy: {_whole(measured['samples'])} chuỗi giả lập 4 ký tự / {duration_ms:.2f} ms",
        f"Tốc độ thực đo: {_whole(rate)} chuỗi/giây",
        f"Ước lượng tại tốc độ này: {_duration(total, rate)}",
        "Lưu ý: Tốc độ tạo chuỗi giả lập, không phải tốc độ dò mật khẩu thật; "
        "độ dài khác, phép băm và phần cứng khác cho kết quả khác.",
        "Không thử đăng nhập, không xử lý mật khẩu, không gửi dữ liệu lên mạng.",
    ))


def run_speed_lab(*, length: int, alphabet_size: int = 74,
                  samples: int = DEFAULT_SAMPLES) -> int:
    try:
        print(speed_report(length, alphabet_size, samples))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
