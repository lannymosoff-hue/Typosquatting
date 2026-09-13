import unittest
from unittest.mock import patch

from typosquat import mutations
from typosquat import main


class TestParseArgs(unittest.TestCase):
    def test_no_args(self) -> None:
        ns = main._parse_args([])
        self.assertIsNone(ns.domain)
        for t in mutations.TYPES:
            self.assertFalse(getattr(ns, t.name))
        self.assertFalse(ns.all_types)
        self.assertFalse(ns.separate)
        self.assertFalse(ns.help)
        self.assertEqual(ns.workers, 20)

    def test_domain_positional(self) -> None:
        self.assertEqual(main._parse_args(["google.com"]).domain, "google.com")

    def test_short_type_flags(self) -> None:
        ns = main._parse_args(["-o", "-r", "-t", "-tld"])
        self.assertTrue(ns.omission and ns.replacement and ns.transposition and ns.tld_swap)

    def test_long_type_flags(self) -> None:
        ns = main._parse_args(["--repetition", "--bitsquatting", "--vowel-swap"])
        self.assertTrue(ns.repetition and ns.bitsquatting and ns.vowel_swap)

    def test_tld_does_not_set_transposition(self) -> None:
        ns = main._parse_args(["-tld"])
        self.assertTrue(ns.tld_swap)
        self.assertFalse(ns.transposition)

    def test_all_and_separate(self) -> None:
        ns = main._parse_args(["-a", "-s"])
        self.assertTrue(ns.all_types and ns.separate)

    def test_export_and_workers(self) -> None:
        ns = main._parse_args(["--json", "o.json", "--csv", "o.csv", "--workers", "8", "--no-cache"])
        self.assertEqual(ns.json_path, "o.json")
        self.assertEqual(ns.csv_path, "o.csv")
        self.assertEqual(ns.workers, 8)
        self.assertTrue(ns.no_cache)

    def test_workers_must_be_positive(self) -> None:
        for bad in ("0", "-3", "x"):
            with self.assertRaises(SystemExit):
                main._parse_args(["--workers", bad])

    def test_help_aliases(self) -> None:
        self.assertTrue(main._parse_args(["-help"]).help)
        self.assertTrue(main._parse_args(["-h"]).help)
        self.assertTrue(main._parse_args(["--help"]).help)


class TestSelectedTypes(unittest.TestCase):
    def test_all_returns_every_type(self) -> None:
        ns = main._parse_args(["-a"])
        self.assertEqual(main._selected_types(ns), list(mutations.ALL_TYPES))

    def test_subset_in_run_order(self) -> None:
        ns = main._parse_args(["-tld", "-o"])
        self.assertEqual(main._selected_types(ns), ["omission", "tld_swap"])

    def test_none_selected(self) -> None:
        self.assertEqual(main._selected_types(main._parse_args([])), [])


class TestRunChecks(unittest.TestCase):
    def _args(self, argv):
        return main._parse_args(argv)

    @patch("typosquat.main._describe_target", return_value=None)
    @patch("typosquat.checker.check_domains", return_value={})
    @patch("typosquat.output.print_summary")
    def test_combined_calls_check_once(self, _sum, mock_check, _desc) -> None:
        main._run_checks("google", ".com", ["omission", "transposition"], self._args([]))
        self.assertEqual(mock_check.call_count, 1)

    @patch("typosquat.main._describe_target", return_value=None)
    @patch("typosquat.checker.check_domains", return_value={})
    @patch("typosquat.output.print_summary")
    def test_combined_deduplicates(self, _sum, mock_check, _desc) -> None:
        main._run_checks("google", ".com", ["omission", "transposition"], self._args([]))
        passed = mock_check.call_args[0][0]
        self.assertEqual(len(passed), len(set(passed)))

    @patch("typosquat.main._describe_target", return_value=None)
    @patch("typosquat.checker.check_domains", return_value={})
    @patch("typosquat.output.print_summary")
    def test_separate_calls_check_per_type(self, _sum, mock_check, _desc) -> None:
        main._run_checks("google", ".com", ["omission", "transposition"], self._args(["-s"]))
        self.assertEqual(mock_check.call_count, 2)

    @patch("typosquat.checker.check_domains", return_value={})
    @patch("typosquat.output.print_summary")
    def test_target_is_described(self, _sum, mock_check) -> None:
        # The scanned domain itself is looked up (one extra check_domains call).
        main._run_checks("google", ".com", ["omission"], self._args([]))
        looked_up = [c.args[0] for c in mock_check.call_args_list]
        self.assertIn(["google.com"], looked_up)


class TestMainOneShot(unittest.TestCase):
    @patch("typosquat.output.print_help")
    def test_help_returns_zero(self, mock_help) -> None:
        self.assertEqual(main.main(["-h"]), 0)
        mock_help.assert_called_once()

    def test_missing_domain_is_usage_error(self) -> None:
        self.assertEqual(main.main(["-o"]), 2)

    def test_no_mutation_flags_is_usage_error(self) -> None:
        self.assertEqual(main.main(["google.com"]), 2)

    def test_unsupported_tld_is_usage_error(self) -> None:
        self.assertEqual(main.main(["google.invalidtld", "-o"]), 2)

    @patch("typosquat.main._run_checks")
    def test_valid_invocation_runs_once(self, mock_run) -> None:
        rc = main.main(["google.com", "-o", "-tld"])
        self.assertEqual(rc, 0)
        mock_run.assert_called_once()
        # types are passed in registry order
        self.assertEqual(mock_run.call_args.args[2], ["omission", "tld_swap"])


if __name__ == "__main__":
    unittest.main()
