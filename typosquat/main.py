"""Typosquatting detection tool.

A one-shot CLI: pass a domain plus one or more mutation-type flags (or -a) and
the scan runs once and exits. See ``typosquat --help`` for the manual.

    typosquat google.com -a --json out.json
    typosquat google.com -o -tld
"""

from __future__ import annotations

import argparse
import sys
import time

from . import checker
from . import mutations
from . import output
from . import parser as domain_parser


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


def _parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="typosquat", usage="typosquat DOMAIN (MUTATION-TYPE... | -a) [OPTIONS]", add_help=False, allow_abbrev=False
    )
    p.add_argument("domain", nargs="?", default=None)
    for mutation in mutations.TYPES:
        p.add_argument(*mutation.flags, dest=mutation.name, action="store_true")
    p.add_argument("-a", "--all", dest="all_types", action="store_true")
    p.add_argument("-s", "--separate", action="store_true")
    p.add_argument("--json", dest="json_path", nargs="?", const="", default=None)
    p.add_argument("--csv", dest="csv_path", nargs="?", const="", default=None)
    p.add_argument("--workers", type=_positive_int, default=checker.DEFAULT_WORKERS)
    p.add_argument("--no-cache", dest="no_cache", action="store_true")
    p.add_argument("--report", dest="report", nargs="?", const="", default=None)
    p.add_argument("-h", "-help", "--help", dest="help", action="store_true")
    return p.parse_args(argv)


def _selected_types(args: argparse.Namespace) -> list[str]:
    if args.all_types:
        return list(mutations.ALL_TYPES)
    return [t.name for t in mutations.TYPES if getattr(args, t.name)]


def _check(candidates: list[str], args: argparse.Namespace) -> dict[str, checker.DomainCheckResult]:
    print(f"Checking {len(candidates)} domain(s)...")
    return checker.check_domains(
        candidates,
        on_progress=output.print_domain_status,
        include_location=True,
        max_workers=args.workers,
        cache_enabled=not args.no_cache,
    )


def _export(target: str, results: dict[str, checker.DomainCheckResult], args: argparse.Namespace) -> None:
    # --json/--csv PATH saves to PATH; bare flag auto-names the file in the current directory.
    if args.json_path is not None:
        path = args.json_path or output.default_export_path(target, "json")
        output.export_json(path, results)
        print(f"\nWrote JSON: {path}")
    if args.csv_path is not None:
        path = args.csv_path or output.default_export_path(target, "csv")
        output.export_csv(path, results)
        print(f"Wrote CSV: {path}")


def _run_checks(sld: str, tld: str, types: list[str], args: argparse.Namespace) -> None:
    start = time.monotonic()
    type_candidates = [(t, mutations.generate(t, sld, tld, domain_parser.TLD_LIST)) for t in types]
    if args.separate:
        groups = [(mutations.LABELS[t], c) for t, c in type_candidates]
    else:
        groups = [("Candidates", list(dict.fromkeys(d for _, c in type_candidates for d in c)))]

    combined_results: dict[str, checker.DomainCheckResult] = {}
    for label, candidates in groups:
        print(f"\n{label}: {len(candidates)}")
        if candidates:
            results = _check(candidates, args)
            output.print_summary(domains=candidates, results_by_domain=results)
            combined_results.update(results)

    target = f"{sld}{tld}"
    target_info = _describe_target(target, args)
    elapsed = time.monotonic() - start
    _export(target, combined_results, args)
    _handle_report(target, type_candidates, combined_results, args, elapsed=elapsed, target_info=target_info)


def _describe_target(target: str, args: argparse.Namespace) -> "checker.DomainCheckResult | None":
    """Look up liveness/IP/location for the original scanned domain."""
    results = checker.check_domains(
        [target],
        include_location=True,
        max_workers=1,
        cache_enabled=not args.no_cache,
    )
    return results.get(target)


def _handle_report(
    target: str,
    type_candidates: "list[tuple[str, list[str]]]",
    results: dict[str, checker.DomainCheckResult],
    args: argparse.Namespace,
    *,
    elapsed: float,
    target_info: "checker.DomainCheckResult | None" = None,
) -> None:
    report = output.build_report(target, type_candidates, results, elapsed_s=elapsed, target_info=target_info)
    print(f"\n{report}")

    # --report PATH saves to PATH; bare --report auto-names the file.
    if args.report is not None:
        path = args.report or output.default_report_path(target)
        output.save_report(path, report)
        print(f"Wrote report: {path}")


def _usage_error(message: str) -> int:
    """Print a usage error to stderr and return the exit code."""
    print(f"error: {message}", file=sys.stderr)
    print("Try 'typosquat --help' for usage.", file=sys.stderr)
    return 2


def main(argv: "list[str] | None" = None) -> int:
    args = _parse_args(argv)

    if args.help:
        output.print_help()
        return 0

    if not args.domain:
        return _usage_error("a domain is required.")

    selected = _selected_types(args)
    if not selected:
        return _usage_error("no mutation types selected; pass at least one type flag (e.g. -o) or -a.")

    sld, tld, host = domain_parser.split_sld_tld(args.domain, domain_parser.TLD_LIST)
    if sld is None or tld is None:
        suffix = domain_parser.extract_tld_suffix(host) if host else None
        output.print_unsupported_tld(host, supported_tlds=domain_parser.TLD_LIST, suffix=suffix)
        return 2

    print(f"\nParsed domain: {sld}{tld}  (SLD={sld!r}, TLD={tld!r})")
    _run_checks(sld, tld, selected, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
