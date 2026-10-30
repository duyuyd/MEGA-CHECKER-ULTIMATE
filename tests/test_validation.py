import unittest
from mega_checker.validation import (
    validate_email, normalize_domain, mask_email, load_disposable_domains
)
from pathlib import Path
from mega_checker.suffixes import get_psl

class ValidationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_email("user@example.com").syntax_status, "valid")
    def test_invalid_shapes(self):
        for value in ("", "abc", "a@@b.com", "@example.com", "a..b@example.com",
                      ".a@example.com", "a.@example.com", "a@-bad.com"):
            self.assertEqual(validate_email(value).syntax_status, "invalid", value)
    def test_too_long_local(self):
        self.assertEqual(validate_email("a"*65 + "@example.com").syntax_status, "invalid")
    def test_idna(self):
        self.assertEqual(normalize_domain("münich.example"), "xn--mnich-kva.example")
        self.assertEqual(validate_email("x@münich.example").syntax_status, "valid")
    def test_public_suffix_and_registrable_domain(self):
        r = validate_email("a@sub.example.co.uk")
        self.assertEqual(r.public_suffix, "co.uk")
        self.assertEqual(r.registrable_domain, "example.co.uk")
        self.assertTrue(r.suffix_known)
    def test_psl_wildcard_exception_rules(self):
        psl = get_psl()
        self.assertIsNotNone(psl)
        self.assertEqual(psl.public_suffix("a.b.ck"), "b.ck")
        self.assertEqual(psl.public_suffix("www.ck"), "ck")
    def test_typo_hint_not_auto_corrected(self):
        r = validate_email("name@gmial.com")
        self.assertEqual(r.typo_suggestion, "name@gmail.com")
        self.assertEqual(r.domain, "gmial.com")
    def test_disposable(self):
        self.assertTrue(validate_email("x@mailinator.com").disposable)
    def test_subdomain_disposable(self):
        ds = {"mailinator.com"}
        self.assertTrue(validate_email("x@sub.mailinator.com", ds).disposable)
    def test_local_part_case_is_preserved(self):
        upper = validate_email("User@example.com")
        lower = validate_email("user@example.com")
        self.assertNotEqual(upper.normalized_email, lower.normalized_email)
    def test_mask(self):
        self.assertEqual(mask_email("someone@example.com"), "s*****e@example.com")
        self.assertEqual(mask_email("a@example.com"), "*@example.com")

if __name__ == "__main__":
    unittest.main()
