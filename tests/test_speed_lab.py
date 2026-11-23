"""Deterministic and bounded checks for the synthetic, local speed lab."""
import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from mega_checker.cli import main
from mega_checker.speed_lab import MAX_SAMPLES, measure_candidate_rate, speed_report


class SpeedLabTests(unittest.TestCase):
    def test_measure_returns_real_nonzero_rate(self):
        result = measure_candidate_rate(2_000)
        self.assertEqual(result['samples'], 2_000)
        self.assertGreater(result['elapsed_ns'], 0)
        self.assertGreater(result['rate_per_second'], 0)

    def test_hard_benchmark_limit(self):
        for size in (0, -1, MAX_SAMPLES + 1, 1.25, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                measure_candidate_rate(size)

    def test_report_counts_and_explains_limitations(self):
        report = speed_report('4', alphabet_size=3, samples=2_000)
        self.assertIn('Độ dài 4 · bảng 3', report)
        self.assertIn('120', report)
        self.assertIn('Tốc độ thực đo', report)
        self.assertIn('không phải tốc độ dò mật khẩu thật', report)
        self.assertIn('Không thử đăng nhập', report)

    def test_invalid_inputs_fail_before_measurement(self):
        with patch('mega_checker.speed_lab.measure_candidate_rate') as measure:
            for length in ('abc', '', '0', '257', '-3'):
                with self.subTest(length=length), self.assertRaises(ValueError):
                    speed_report(length)
            for alphabet in (0, -1, 1_114_113, True):
                with self.subTest(alphabet=alphabet), self.assertRaises(ValueError):
                    speed_report('8', alphabet_size=alphabet)
            measure.assert_not_called()

    def test_cli_speed_lab_offline(self):
        output, err = io.StringIO(), io.StringIO()
        with patch('socket.socket.connect', side_effect=AssertionError('network')), \
                redirect_stdout(output), redirect_stderr(err):
            status = main(['speed-lab', '--length', '6', '--alphabet-size', '74', '--samples', '2000'])
        self.assertEqual(status, 0, err.getvalue())
        self.assertIn('Tốc độ thực đo', output.getvalue())
        self.assertIn('Không thử đăng nhập', output.getvalue())

    def test_cli_rejects_invalid_samples(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(['speed-lab', '--length', '8', '--samples', str(MAX_SAMPLES + 1)])
        self.assertEqual(status, 2)
        self.assertIn('Số mẫu phải', err.getvalue())

    def test_menu_speed_option_without_external_config(self):
        output, err = io.StringIO(), io.StringIO()
        with patch('builtins.input', side_effect=['8', '6', '74']), \
                patch('socket.socket.connect', side_effect=AssertionError('network')), \
                redirect_stdout(output), redirect_stderr(err):
            status = main(['menu'])
        self.assertEqual(status, 0, err.getvalue())
        self.assertIn('Tốc độ thực đo', output.getvalue())

    def test_exact_rate_is_not_hardcoded(self):
        with patch('mega_checker.speed_lab.perf_counter_ns', side_effect=[0, 200_000_000]):
            result = measure_candidate_rate(2000)
        self.assertEqual(result['rate_per_second'], 10_000)
        self.assertEqual(result['elapsed_ns'], 200_000_000)
