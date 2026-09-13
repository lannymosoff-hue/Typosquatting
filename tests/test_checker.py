import socket
import unittest
from unittest.mock import MagicMock, patch

import requests

from typosquat import checker
from typosquat import parser


def _make_session(status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    session = MagicMock()
    session.head.return_value = response
    session.get.return_value = response
    return session


class TestLinkExists(unittest.TestCase):
    def test_returns_true_for_200(self) -> None:
        self.assertTrue(checker.link_exists("https://example.com", session=_make_session(200)))

    def test_returns_true_for_301(self) -> None:
        self.assertTrue(checker.link_exists("https://example.com", session=_make_session(301)))

    def test_returns_false_for_404(self) -> None:
        self.assertFalse(checker.link_exists("https://example.com", session=_make_session(404)))

    def test_returns_false_for_500(self) -> None:
        self.assertFalse(checker.link_exists("https://example.com", session=_make_session(500)))

    def test_returns_false_on_request_exception(self) -> None:
        session = MagicMock()
        session.head.side_effect = requests.RequestException("timeout")
        self.assertFalse(checker.link_exists("https://example.com", session=session))

    def test_raises_value_error_without_scheme(self) -> None:
        with self.assertRaises(ValueError):
            checker.link_exists("example.com")

    def test_accepts_http_scheme(self) -> None:
        self.assertTrue(checker.link_exists("http://example.com", session=_make_session(200)))


class TestLookupIpLocation(unittest.TestCase):
    def test_rejects_non_ip_string(self) -> None:
        self.assertIsNone(checker.lookup_ip_location("1.2.3.4/../../etc"))

    def test_rejects_hostname(self) -> None:
        self.assertIsNone(checker.lookup_ip_location("example.com"))

    def test_rejects_empty_string(self) -> None:
        self.assertIsNone(checker.lookup_ip_location(""))


class TestNormalizeHost(unittest.TestCase):
    def test_plain_domain(self) -> None:
        self.assertEqual(parser.normalize_host("example.com"), "example.com")

    def test_strips_https_scheme(self) -> None:
        self.assertEqual(parser.normalize_host("https://example.com"), "example.com")

    def test_strips_path(self) -> None:
        self.assertEqual(parser.normalize_host("https://example.com/path"), "example.com")

    def test_strips_port(self) -> None:
        self.assertEqual(parser.normalize_host("example.com:8080"), "example.com")

    def test_strips_trailing_dot(self) -> None:
        self.assertEqual(parser.normalize_host("example.com."), "example.com")

    def test_lowercases(self) -> None:
        self.assertEqual(parser.normalize_host("EXAMPLE.COM"), "example.com")

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(parser.normalize_host(""))

    def test_whitespace_only_returns_none(self) -> None:
        self.assertIsNone(parser.normalize_host("   "))


class TestResolveIps(unittest.TestCase):
    def test_returns_ips_from_getaddrinfo(self) -> None:
        mock_infos = [
            (None, None, None, None, ("1.2.3.4", 0)),
            (None, None, None, None, ("5.6.7.8", 0)),
        ]
        with patch("socket.getaddrinfo", return_value=mock_infos):
            self.assertEqual(checker.resolve_ips("example.com"), ("1.2.3.4", "5.6.7.8"))

    def test_deduplicates_ips(self) -> None:
        mock_infos = [
            (None, None, None, None, ("1.2.3.4", 0)),
            (None, None, None, None, ("1.2.3.4", 0)),
        ]
        with patch("socket.getaddrinfo", return_value=mock_infos):
            self.assertEqual(checker.resolve_ips("example.com"), ("1.2.3.4",))

    def test_returns_empty_on_failure(self) -> None:
        with patch("socket.getaddrinfo", side_effect=OSError):
            self.assertEqual(checker.resolve_ips("nonexistent.invalid"), ())

    def test_empty_domain(self) -> None:
        self.assertEqual(checker.resolve_ips(""), ())

    def test_ipv6_included(self) -> None:
        mock_infos = [
            (None, None, None, None, ("::1", 0, 0, 0)),
            (None, None, None, None, ("1.2.3.4", 0)),
        ]
        with patch("socket.getaddrinfo", return_value=mock_infos):
            result = checker.resolve_ips("localhost")
        self.assertIn("::1", result)
        self.assertIn("1.2.3.4", result)


class TestCheckDomains(unittest.TestCase):
    def test_dns_first_skips_http_for_unresolved(self) -> None:
        with patch("typosquat.checker.resolve_ips", return_value=()) as mock_resolve, \
             patch("typosquat.checker.link_exists") as mock_link:
            results = checker.check_domains(
                ["dead.com"], include_location=False, cache_enabled=False, max_workers=2
            )
        mock_resolve.assert_called_once()
        mock_link.assert_not_called()
        self.assertFalse(results["dead.com"].live)

    def test_probes_resolved_domains(self) -> None:
        with patch("typosquat.checker.resolve_ips", return_value=("1.2.3.4",)), \
             patch("typosquat.checker.link_exists", return_value=True), \
             patch("typosquat.checker.lookup_ip_location", return_value="City, Country"):
            results = checker.check_domains(
                ["live.com"], include_location=True, cache_enabled=False, max_workers=2
            )
        r = results["live.com"]
        self.assertTrue(r.https_live and r.http_live and r.live)
        self.assertEqual(r.ips, ("1.2.3.4",))
        self.assertEqual(r.location, "City, Country")

    def test_progress_callback_invoked_per_domain(self) -> None:
        calls = []
        with patch("typosquat.checker.resolve_ips", return_value=()):
            checker.check_domains(
                ["a.com", "b.com"],
                include_location=False,
                cache_enabled=False,
                max_workers=2,
                on_progress=lambda *args: calls.append(args[2]),
            )
        self.assertEqual(set(calls), {"a.com", "b.com"})

    def test_empty_input(self) -> None:
        self.assertEqual(checker.check_domains([], cache_enabled=False), {})


if __name__ == "__main__":
    unittest.main()
