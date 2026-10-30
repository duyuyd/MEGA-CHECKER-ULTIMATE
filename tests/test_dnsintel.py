from mega_checker.dnsintel import dkim_selectors_for_domain
import unittest
import io
import json
import urllib.parse
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mega_checker import dnsintel
from mega_checker.dnsintel import DomainInspector, _CloudflareDoHResolver


class DNSInspectorTests(unittest.TestCase):
    def _inspect_mx(self, answers):
        fake_resolver = Mock()
        fake_resolver.resolve.return_value = answers
        inspector = DomainInspector()
        with patch("mega_checker.dnsintel.dns.resolver.Resolver", return_value=fake_resolver):
            with patch.object(inspector, "_resolve_txt", return_value=([], "absent")):
                return inspector._inspect_with_dnspython("example.invalid")

    def test_null_mx_is_not_reported_as_mail_host(self):
        result = self._inspect_mx([
            SimpleNamespace(exchange=".", preference=0)
        ])
        self.assertEqual(result["mx_status"], "null_mx")
        self.assertEqual(result["mx_hosts"], [])

    def test_null_mx_mixed_with_regular_mx_is_flagged(self):
        result = self._inspect_mx([
            SimpleNamespace(exchange=".", preference=0),
            SimpleNamespace(exchange="mx.example.invalid.", preference=10),
        ])
        self.assertEqual(result["mx_status"], "invalid_mx_configuration")
        self.assertEqual(result["mx_hosts"], ["mx.example.invalid"])

    def test_android_dns_property_values_are_validated_and_deduplicated(self):
        outputs = {
            "net.dns1": "1.1.1.1\n",
            "net.dns2": "2001:4860:4860::8888\n",
            "net.dns3": "not-an-ip\n",
            "net.dns4": "1.1.1.1\n",
        }

        def fake_run(args, **kwargs):
            value = outputs[args[1]]
            return SimpleNamespace(stdout=value, returncode=0)

        with patch.object(dnsintel, "_ANDROID_DNS_CACHE", (0.0, ())):
            with patch.object(dnsintel.subprocess, "run", side_effect=fake_run):
                self.assertEqual(
                    dnsintel._android_dns_nameservers(),
                    ["1.1.1.1", "2001:4860:4860::8888"],
                )

    def test_resolver_uses_android_dns_without_resolv_conf(self):
        fake_resolver = Mock()
        inspector = DomainInspector()
        with patch("mega_checker.dnsintel._android_dns_nameservers", return_value=["192.0.2.53"]):
            with patch("mega_checker.dnsintel.dns.resolver.Resolver", return_value=fake_resolver) as factory:
                resolver, provider = inspector._create_resolver()
        factory.assert_called_once_with(configure=False)
        self.assertEqual(fake_resolver.nameservers, ["192.0.2.53"])
        self.assertEqual(provider, "android_getprop")

    def test_no_android_or_system_dns_returns_structured_unconfigured_state(self):
        inspector = DomainInspector()
        empty_resolver = Mock()
        empty_resolver.nameservers = []
        with patch("mega_checker.dnsintel._android_dns_nameservers", return_value=[]):
            with patch(
                "mega_checker.dnsintel.dns.resolver.Resolver",
                side_effect=[dnsintel.dns.resolver.NoResolverConfiguration("missing"), empty_resolver],
            ):
                with patch.dict("os.environ", {"MEGA_CHECKER_DOH": "0"}):
                    result = inspector._inspect_with_dnspython("example.invalid")
        self.assertEqual(result["dns_status"], "resolver_unconfigured")
        self.assertEqual(result["mx_status"], "resolver_unconfigured")


    def test_resolver_falls_back_to_doh_when_no_resolv_conf(self):
        inspector = DomainInspector(timeout=3)
        with patch("mega_checker.dnsintel._android_dns_nameservers", return_value=[]):
            with patch(
                "mega_checker.dnsintel.dns.resolver.Resolver",
                side_effect=dnsintel.dns.resolver.NoResolverConfiguration("missing"),
            ):
                resolver, provider = inspector._create_resolver()
        self.assertIsInstance(resolver, _CloudflareDoHResolver)
        self.assertEqual(provider, "cloudflare_doh")

    def test_doh_resolver_parses_mx_and_txt_records(self):
        resolver = _CloudflareDoHResolver(timeout=3)
        payloads = {
            "MX": {
                "Status": 0,
                "Answer": [{"type": 15, "data": "5 gmail-smtp-in.l.google.com."}],
            },
            "TXT": {
                "Status": 0,
                "Answer": [{"type": 16, "data": '"v=spf1 include:_spf.google.com ~all"'}],
            },
        }

        def fake_urlopen(request, **_kwargs):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
            kind = query["type"][0]
            return io.BytesIO(json.dumps(payloads[kind]).encode("utf-8"))

        with patch("mega_checker.dnsintel.urllib.request.urlopen", side_effect=fake_urlopen):
            mx = resolver.resolve("gmail.com", "MX")
            txt = resolver.resolve("gmail.com", "TXT")
        self.assertEqual(str(mx[0].exchange), "gmail-smtp-in.l.google.com.")
        self.assertEqual(int(mx[0].preference), 5)
        self.assertEqual(txt[0].strings, (b"v=spf1 include:_spf.google.com ~all",))

    def test_doh_resolver_maps_nxdomain_and_no_answer(self):
        resolver = _CloudflareDoHResolver(timeout=3)
        responses = [
            {"Status": 3, "Answer": []},
            {"Status": 0, "Answer": []},
        ]
        def fake_urlopen(_request, **_kwargs):
            return io.BytesIO(json.dumps(responses.pop(0)).encode("utf-8"))
        with patch("mega_checker.dnsintel.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(dnsintel.dns.resolver.NXDOMAIN):
                resolver.resolve("missing.invalid", "MX")
            with self.assertRaises(dnsintel.dns.resolver.NoAnswer):
                resolver.resolve("example.com", "MX")

    def test_doh_resolver_maps_timeout(self):
        import socket
        resolver = _CloudflareDoHResolver(timeout=3)
        with patch(
            "mega_checker.dnsintel.urllib.request.urlopen",
            side_effect=socket.timeout("timed out"),
        ):
            with self.assertRaises(dnsintel.dns.exception.Timeout):
                resolver.resolve("gmail.com", "MX")



    def test_domain_inspector_uses_doh_for_full_mx_spf_dmarc_flow(self):
        inspector = DomainInspector(timeout=2)

        def fake_urlopen(request, **_kwargs):
            query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
            name, kind = query["name"][0], query["type"][0]
            if kind == "MX":
                payload = {"Status": 0, "Answer": [
                    {"type": 15, "data": "10 mail.example.com."}
                ]}
            elif kind == "TXT" and name == "example.com":
                payload = {"Status": 0, "Answer": [
                    {"type": 16, "data": '"v=spf1 -all"'}
                ]}
            elif kind == "TXT" and name == "_dmarc.example.com":
                payload = {"Status": 0, "Answer": [
                    {"type": 16, "data": '"v=DMARC1; p=reject"'}
                ]}
            else:
                payload = {"Status": 0, "Answer": []}
            return io.BytesIO(json.dumps(payload).encode("utf-8"))

        with patch("mega_checker.dnsintel._android_dns_nameservers", return_value=[]):
            with patch(
                "mega_checker.dnsintel.dns.resolver.Resolver",
                side_effect=dnsintel.dns.resolver.NoResolverConfiguration("missing"),
            ):
                with patch("mega_checker.dnsintel.urllib.request.urlopen", side_effect=fake_urlopen):
                    result = inspector.inspect("example.com")

        self.assertEqual(result["dns_provider"], "cloudflare_doh")
        self.assertEqual(result["mx_status"], "found")
        self.assertEqual(result["mx_hosts"], ["mail.example.com"])
        self.assertEqual(result["spf_status"], "present")
        self.assertEqual(result["dmarc_status"], "present")
        self.assertEqual(result["dkim_status"], "not_found_in_tested_selectors")


    def test_gmail_selector_hints_are_provider_scoped(self):
        gmail = dkim_selectors_for_domain("gmail.com")
        self.assertIn("20251104", gmail)
        self.assertIn("20230601", gmail)
        self.assertIn("20221208", gmail)
        self.assertNotIn("20251104", dkim_selectors_for_domain("example.com"))


if __name__ == "__main__":
    unittest.main()
