import unittest

from typosquat import parser


class TestSplitSldTld(unittest.TestCase):
    TLDS = [".com", ".net", ".co.uk", ".org"]

    def test_simple_domain(self) -> None:
        sld, tld, host = parser.split_sld_tld("example.com", self.TLDS)
        self.assertEqual((sld, tld, host), ("example", ".com", "example.com"))

    def test_url_with_https_scheme(self) -> None:
        sld, tld, _ = parser.split_sld_tld("https://example.com", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_url_with_path(self) -> None:
        sld, tld, _ = parser.split_sld_tld("https://example.com/some/path", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_url_with_port(self) -> None:
        sld, tld, _ = parser.split_sld_tld("example.com:8080", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_www_subdomain_ignored(self) -> None:
        sld, tld, _ = parser.split_sld_tld("www.example.com", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_multi_label_subdomain_ignored(self) -> None:
        sld, tld, _ = parser.split_sld_tld("a.b.example.com", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_multi_part_tld(self) -> None:
        sld, tld, _ = parser.split_sld_tld("example.co.uk", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".co.uk"))

    def test_multi_part_tld_preferred_over_shorter(self) -> None:
        sld, tld, _ = parser.split_sld_tld("example.co.uk", [".uk", ".co.uk"])
        self.assertEqual(tld, ".co.uk")

    def test_unsupported_tld(self) -> None:
        sld, tld, host = parser.split_sld_tld("example.invalid", self.TLDS)
        self.assertIsNone(sld)
        self.assertIsNone(tld)
        self.assertEqual(host, "example.invalid")

    def test_empty_input(self) -> None:
        self.assertEqual(parser.split_sld_tld("", self.TLDS), (None, None, None))

    def test_trailing_dot_stripped(self) -> None:
        sld, tld, _ = parser.split_sld_tld("example.com.", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))

    def test_tld_only(self) -> None:
        sld, tld, _ = parser.split_sld_tld(".com", self.TLDS)
        self.assertIsNone(sld)
        self.assertIsNone(tld)

    def test_case_insensitive(self) -> None:
        sld, tld, _ = parser.split_sld_tld("EXAMPLE.COM", self.TLDS)
        self.assertEqual((sld, tld), ("example", ".com"))


class TestExtractTldSuffix(unittest.TestCase):
    def test_normal_domain(self) -> None:
        self.assertEqual(parser.extract_tld_suffix("example.xyz"), ".xyz")

    def test_multi_part_returns_last_label(self) -> None:
        self.assertEqual(parser.extract_tld_suffix("example.co.uk"), ".uk")

    def test_no_dot_returns_whole_string(self) -> None:
        self.assertEqual(parser.extract_tld_suffix("localhost"), "localhost")


if __name__ == "__main__":
    unittest.main()
