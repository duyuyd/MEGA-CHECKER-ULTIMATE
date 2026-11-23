import getpass
import io
import tempfile
import unittest
import warnings
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from mega_checker.cli import main
from mega_checker.password_lab import MAX_ALPHABET, MAX_LENGTH, combination_counts, password_report


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


class PasswordLabTests(unittest.TestCase):
    def test_counts_match_the_video_and_include_shorter_lengths(self):
        self.assertEqual(combination_counts(5, 48), (254_803_968, 260_225_328))
        self.assertEqual(combination_counts(7, 74), (12_151_280_273_024, 12_317_736_167_174))

    def test_degenerate_and_boundary_cases(self):
        self.assertEqual(combination_counts(1, 48), (48, 48))
        self.assertEqual(combination_counts(4, 1), (1, 4))
        with self.subTest("large integer arithmetic"):
            exact, total = combination_counts(MAX_LENGTH, MAX_ALPHABET)
            self.assertEqual(exact, MAX_ALPHABET ** MAX_LENGTH)
            self.assertEqual(total, sum(MAX_ALPHABET ** n for n in range(1, MAX_LENGTH + 1)))
            code, out, err = run_cli("password-lab", "--length", str(MAX_LENGTH),
                                     "--alphabet-size", str(MAX_ALPHABET))
            self.assertEqual(code, 0, err)
            self.assertIn("năm", out)

    def test_length_and_alphabet_limits(self):
        for length, alphabet in ((0, 48), (-1, 48), (MAX_LENGTH + 1, 2), (5, 0), (5, MAX_ALPHABET + 1)):
            with self.subTest(length=length, alphabet=alphabet), self.assertRaises(ValueError):
                combination_counts(length, alphabet)

    def test_default_and_private_menu_use_the_actual_input_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            flags = ("--config", str(folder / "config.json"), "--db", str(folder / "data.db"))
            with patch("socket.socket.connect", side_effect=AssertionError("network")), \
                    patch("sys.stdin.isatty", return_value=True), \
                    patch("getpass.getpass", return_value="abababab"), patch("builtins.input", return_value="7"):
                for args in (("password-lab",), (), ("menu",)):
                    code, out, err = run_cli(*flags, *args)
                    self.assertEqual(code, 0, err)
                    self.assertIn("8 ký tự · 2 ký tự khác nhau", out)
                    self.assertIn("lặp lại cùng một cụm", out)
                    self.assertNotIn("abababab", out + err)
            self.assertEqual(list(folder.iterdir()), [])

    def test_numeric_menu_uses_supplied_dimensions(self):
        with patch("builtins.input", side_effect=["6", "2", "3"]):
            code, out, err = run_cli("menu")
        self.assertEqual(code, 0, err)
        self.assertIn("12 chuỗi", out)

    def test_patterns_and_real_measurement(self):
        self.assertIn("phím liền kề", password_report("xy4321ab"))
        self.assertIn("khoảng trắng", password_report("    "))
        self.assertIn("bốn ký tự", password_report("aaaa test"))
        natural = password_report("Giữa hồ sen, trời xanh!")
        self.assertIn("Thời gian phân tích trên máy", natural)
        self.assertNotIn("Giữa hồ", natural)

    def test_rate_only_changes_estimated_duration(self):
        args = ("password-lab", "--length", "2", "--alphabet-size", "3", "--rate")
        for rate, duration in (("6", "2,00 giây"), ("24", "500,00 ms"), ("100000", "< 1 ms")):
            with self.subTest(rate=rate):
                code, out, err = run_cli(*args, rate)
                self.assertEqual(code, 0, err)
                self.assertIn("12 chuỗi", out)
                self.assertIn(duration, out)

    def test_invalid_cli_combinations_and_rates(self):
        for flags in (("--length", "5"), ("--alphabet-size", "48"), ("--rate", "0"), ("--rate", "-2")):
            with self.subTest(flags=flags):
                self.assertEqual(run_cli("password-lab", *flags)[0], 2)

    def test_hidden_input_uses_video_groups_and_only_emits_counts(self):
        sample = "T9x!q"
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", return_value=sample), \
                patch("builtins.input", return_value="7"), \
                patch("mega_checker.cli.load_config", side_effect=AssertionError("config")), \
                patch("socket.socket.connect", side_effect=AssertionError("network")):
            code, out, err = run_cli("menu")
        self.assertEqual(code, 0, err)
        self.assertIn("5 ký tự · 5 ký tự khác nhau", out)
        self.assertIn("bảng 74 ký tự", out)
        self.assertNotIn(sample, out + err)

    def test_custom_unicode_alphabet_and_spaces(self):
        sample = " Đỏ "
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", return_value=sample), \
                patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
            code, out, err = run_cli("password-lab", "--prompt")
            self.assertEqual(code, 0, err)
            self.assertIn("4 ký tự · 3 ký tự khác nhau", out)
            code, out, err = run_cli("password-lab", "--prompt", "--alphabet-size", "10")
            self.assertEqual(code, 0, err)
            self.assertIn("11.110 chuỗi", out)
            self.assertNotIn(sample, out + err)
            code, out, err = run_cli("password-lab", "--prompt", "--alphabet-size", "2")
            self.assertEqual(code, 2)
            self.assertNotIn(sample, out + err)

    def test_private_prompt_does_not_read_a_pipe_or_fall_back_to_echo(self):
        with patch("sys.stdin.isatty", return_value=False), patch("getpass.getpass") as read:
            self.assertEqual(run_cli("password-lab", "--prompt")[0], 2)
            read.assert_not_called()

        def warn_before_visible_input(_prompt):
            warnings.warn("Echo is enabled", getpass.GetPassWarning)
            self.fail("Reached a visible password prompt")

        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", warn_before_visible_input):
            self.assertEqual(run_cli("password-lab", "--prompt")[0], 2)

    def test_cancelled_closed_or_empty_private_input(self):
        for error, expected in ((KeyboardInterrupt(), 130), (EOFError(), 2)):
            with self.subTest(error=error), patch("sys.stdin.isatty", return_value=True), \
                    patch("getpass.getpass", side_effect=error):
                self.assertEqual(run_cli("password-lab", "--prompt")[0], expected)
        with patch("sys.stdin.isatty", return_value=True), patch("getpass.getpass", return_value=""):
            self.assertEqual(run_cli("password-lab", "--prompt")[0], 2)
