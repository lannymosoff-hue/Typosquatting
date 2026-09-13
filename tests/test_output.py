import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from typosquat import output
from typosquat.checker import DomainCheckResult


class TestPrintHelp(unittest.TestCase):
    def _capture(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            output.print_help()
        return buf.getvalue()

    def test_is_man_page(self) -> None:
        text = self._capture()
        for section in ["NAME", "SYNOPSIS", "DESCRIPTION", "OPTIONS", "EXAMPLES"]:
            self.assertIn(section, text)

    def test_contains_core_flags(self) -> None:
        text = self._capture()
        for flag in ["-o", "-r", "-t", "-tld", "-a", "-s", "--json", "--csv", "--help"]:
            self.assertIn(flag, text)

    def test_contains_new_types(self) -> None:
        text = self._capture()
        for flag in ["--bitsquatting", "--vowel-swap", "--insertion"]:
            self.assertIn(flag, text)


def _results() -> dict:
    return {
        "live.com": DomainCheckResult("live.com", True, False, ("1.2.3.4",), "City, Country"),
        "dead.com": DomainCheckResult("dead.com", False, False, (), None),
    }


class TestSummary(unittest.TestCase):
    def test_counts(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            output.print_summary(domains=["live.com", "dead.com"], results_by_domain=_results())
        text = buf.getvalue()
        self.assertIn("Live (any):  1", text)
        self.assertIn("live.com", text)
        self.assertNotIn("\n  - dead.com", text)


class TestExport(unittest.TestCase):
    def test_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.json"
            output.export_json(path, _results())
            data = json.loads(path.read_text())
        rows = {row["domain"]: row for row in data}
        self.assertTrue(rows["live.com"]["live"])
        self.assertEqual(rows["live.com"]["ips"], ["1.2.3.4"])
        self.assertFalse(rows["dead.com"]["live"])

    def test_csv(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.csv"
            output.export_csv(path, _results())
            with open(path, newline="") as fh:
                rows = list(csv.DictReader(fh))
        by_domain = {r["domain"]: r for r in rows}
        self.assertEqual(by_domain["live.com"]["https_live"], "True")
        self.assertEqual(by_domain["live.com"]["ips"], "1.2.3.4")


if __name__ == "__main__":
    unittest.main()


class TestReport(unittest.TestCase):
    def _data(self):
        type_candidates = [
            ("omission", ["live.com", "dead.com"]),
            ("tld_swap", ["dead.com"]),
        ]
        return type_candidates, _results()

    def test_build_report_contents(self) -> None:
        tc, results = self._data()
        report = output.build_report("google.com", tc, results, elapsed_s=1.5)
        self.assertIn("TYPOSQUATTING SCAN REPORT", report)
        self.assertIn("google.com", report)
        self.assertIn("Duration:      1.5s", report)
        self.assertIn("Candidates checked:  2", report)  # deduped across types
        self.assertIn("Live (any):          1", report)
        self.assertIn("Omission", report)
        self.assertIn("- live.com", report)

    def test_build_report_no_live(self) -> None:
        tc = [("omission", ["dead.com"])]
        results = {"dead.com": DomainCheckResult("dead.com", False, False, (), None)}
        report = output.build_report("x.com", tc, results)
        self.assertIn("Live domains: none found.", report)

    def test_default_report_path_sanitized(self) -> None:
        path = output.default_report_path("google.com")
        self.assertTrue(path.startswith("report_google.com_"))
        self.assertTrue(path.endswith(".txt"))

    def test_save_report(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "r.txt"
            output.save_report(path, "hello report")
            self.assertEqual(path.read_text().strip(), "hello report")


class TestReportTargetInfo(unittest.TestCase):
    def test_target_info_section(self) -> None:
        tc = [("omission", ["dead.com"])]
        results = {"dead.com": DomainCheckResult("dead.com", False, False, (), None)}
        info = DomainCheckResult("google.com", True, True, ("8.8.8.8", "8.8.4.4"), "Mountain View, US")
        report = output.build_report("google.com", tc, results, target_info=info)
        self.assertIn("Scanned domain", report)
        self.assertIn("Status:        online", report)
        self.assertIn("IP address:    8.8.8.8", report)
        self.assertIn("Other IPs:     8.8.4.4", report)
        self.assertIn("Mountain View, US", report)

    def test_target_info_absent(self) -> None:
        report = output.build_report("x.com", [("omission", [])], {}, target_info=None)
        self.assertIn("Scanned domain", report)
        self.assertIn("(not checked)", report)


class TestHelpMutationTypes(unittest.TestCase):
    def _capture(self) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            output.print_help()
        return buf.getvalue()

    def test_lists_types_with_examples(self) -> None:
        text = self._capture()
        self.assertIn("MUTATION TYPES", text)
        self.assertIn("--omission", text)
        self.assertIn("Drop one character", text)
        self.assertIn("google -> gogle", text)
        self.assertIn("--bitsquatting", text)
        self.assertIn("--tld-swap", text)
