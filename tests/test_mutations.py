import unittest

from typosquat import mutations


class TestOmission(unittest.TestCase):
    def test_empty_and_single(self) -> None:
        self.assertEqual(mutations.generate_omission(""), [])
        self.assertEqual(mutations.generate_omission("a"), [])

    def test_dedup(self) -> None:
        self.assertEqual(mutations.generate_omission("aa"), ["a"])

    def test_no_original(self) -> None:
        self.assertNotIn("google", mutations.generate_omission("google"))
        self.assertIn("gogle", mutations.generate_omission("google"))


class TestReplacement(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(mutations.generate_replacement(""), [])
        self.assertEqual(mutations.generate_replacement("   "), [])

    def test_single_char(self) -> None:
        self.assertEqual(mutations.generate_replacement("a"), ["q", "s", "w", "z"])

    def test_no_original(self) -> None:
        self.assertNotIn("google", mutations.generate_replacement("google"))


class TestTransposition(unittest.TestCase):
    def test_empty_and_single(self) -> None:
        self.assertEqual(mutations.generate_transposition(""), [])
        self.assertEqual(mutations.generate_transposition("a"), [])

    def test_two_chars(self) -> None:
        self.assertEqual(mutations.generate_transposition("ab"), ["ba"])

    def test_identical_skipped(self) -> None:
        self.assertEqual(mutations.generate_transposition("aa"), [])

    def test_google(self) -> None:
        self.assertEqual(
            mutations.generate_transposition("google"),
            ["ogogle", "gogole", "goolge", "googel"],
        )

    def test_dedup(self) -> None:
        variants = mutations.generate_transposition("abab")
        self.assertEqual(len(variants), len(set(variants)))


class TestInsertion(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertEqual(mutations.generate_insertion(""), [])

    def test_no_original_and_longer(self) -> None:
        variants = mutations.generate_insertion("go")
        self.assertNotIn("go", variants)
        self.assertTrue(all(len(v) == 3 for v in variants))


class TestRepetition(unittest.TestCase):
    def test_doubles(self) -> None:
        self.assertEqual(mutations.generate_repetition("ab"), ["aab", "abb"])

    def test_dedup(self) -> None:
        self.assertEqual(mutations.generate_repetition("aa"), ["aaa"])


class TestVowelSwap(unittest.TestCase):
    def test_no_vowels(self) -> None:
        self.assertEqual(mutations.generate_vowel_swap("xyz"), [])

    def test_swaps(self) -> None:
        self.assertEqual(mutations.generate_vowel_swap("a"), ["e", "i", "o", "u"])


class TestHyphenation(unittest.TestCase):
    def test_empty_and_single(self) -> None:
        self.assertEqual(mutations.generate_hyphenation(""), [])
        self.assertEqual(mutations.generate_hyphenation("a"), [])

    def test_inserts_hyphen(self) -> None:
        self.assertEqual(mutations.generate_hyphenation("ab"), ["a-b"])


class TestAddition(unittest.TestCase):
    def test_appends(self) -> None:
        variants = mutations.generate_addition("go")
        self.assertIn("goa", variants)
        self.assertIn("goz", variants)
        self.assertEqual(len(variants), 26)


class TestBitsquatting(unittest.TestCase):
    def test_only_valid_label_chars(self) -> None:
        for variant in mutations.generate_bitsquatting("google"):
            self.assertTrue(all(c in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in variant))

    def test_no_original(self) -> None:
        self.assertNotIn("google", mutations.generate_bitsquatting("google"))


class TestTldSwap(unittest.TestCase):
    def test_excludes_current(self) -> None:
        result = mutations.generate_tld_swaps("google", ".com", [".com", ".net", ".org"])
        self.assertEqual(result, ["google.net", "google.org"])


class TestBuildDomains(unittest.TestCase):
    def test_normalizes_tld(self) -> None:
        self.assertEqual(mutations.build_domains(["gogle"], ".com"), ["gogle.com"])
        self.assertEqual(mutations.build_domains(["gogle"], "com"), ["gogle.com"])
        self.assertEqual(mutations.build_domains([], "com"), [])


class TestRegistry(unittest.TestCase):
    def test_all_types_present(self) -> None:
        for name in mutations.ALL_TYPES:
            self.assertIn(name, mutations.LABELS)

    def test_generate_dispatch(self) -> None:
        tlds = [".com", ".net"]
        self.assertIn("gogle.com", mutations.generate("omission", "google", ".com", tlds))
        self.assertIn("google.net", mutations.generate("tld_swap", "google", ".com", tlds))

    def test_generate_unknown_type(self) -> None:
        self.assertEqual(mutations.generate("nope", "google", ".com", [".com"]), [])


if __name__ == "__main__":
    unittest.main()
