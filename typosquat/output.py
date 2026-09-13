"""Console rendering and file export for the one-shot CLI."""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from . import mutations
from .checker import DomainCheckResult


# --------------------------------------------------------------------------- #
# Status / progress output
# --------------------------------------------------------------------------- #
def print_unsupported_tld(host: "str | None", *, supported_tlds: list[str], suffix: "str | None") -> None:
    if host and suffix:
        print(f"error: unsupported TLD {suffix!r} in {host!r}.", file=sys.stderr)
        print(
            f"Supported TLDs: {len(supported_tlds)} configured (edit the list in parser.py).",
            file=sys.stderr,
        )
    else:
        print("error: could not parse a domain from that input.", file=sys.stderr)


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: max(0, width - 3)] + "..." if width > 3 else text[:width]


def _status_line(domain: str, https_live: bool, http_live: bool, ip: "str | None", location: "str | None", *, prefix: str = "") -> str:
    https_text = "LIVE" if https_live else "dead"
    http_text = "LIVE" if http_live else "dead"
    return (
        f"{prefix}{_truncate(domain, 32):<32}  "
        f"HTTPS:{https_text:<4}  HTTP:{http_text:<4}  "
        f"IP:{_truncate(ip or '-', 39):<15}  {location or '-'}"
    )


def print_domain_status(
    index: int,
    total: int,
    domain: str,
    https_live: bool,
    http_live: bool,
    ips: tuple[str, ...],
    location: "str | None",
) -> None:
    prefix = f"[{index:>3}/{total:<3}] "
    print(_status_line(domain, https_live, http_live, ips[0] if ips else None, location, prefix=prefix))


def print_summary(*, domains: list[str], results_by_domain: dict[str, DomainCheckResult]) -> None:
    live = [results_by_domain[d] for d in domains if d in results_by_domain and results_by_domain[d].live]
    https_count = sum(1 for r in live if r.https_live)
    http_count = sum(1 for r in live if r.http_live)

    print("\nResults")
    print(f"  Checked:     {len(domains)}")
    print(f"  Live (any):  {len(live)}")
    print(f"  HTTPS live:  {https_count}")
    print(f"  HTTP live:   {http_count}")

    if not live:
        print("\nNo live domains found.")
        return

    print("\nLive domains")
    for r in live:
        print(_status_line(r.domain, r.https_live, r.http_live, r.ips[0] if r.ips else None, r.location, prefix="  - "))


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def export_json(path: "str | Path", results_by_domain: dict[str, DomainCheckResult]) -> None:
    rows = [{**asdict(r), "live": r.live, "ips": list(r.ips)} for r in results_by_domain.values()]
    Path(path).write_text(json.dumps(rows, indent=2), encoding="utf-8")


def export_csv(path: "str | Path", results_by_domain: dict[str, DomainCheckResult]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["domain", "https_live", "http_live", "live", "ips", "location"])
        for r in results_by_domain.values():
            writer.writerow([r.domain, r.https_live, r.http_live, r.live, " ".join(r.ips), r.location or ""])


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def build_report(
    target: str,
    type_candidates: "list[tuple[str, list[str]]]",
    results_by_domain: dict[str, DomainCheckResult],
    *,
    elapsed_s: "float | None" = None,
    target_info: "DomainCheckResult | None" = None,
) -> str:
    """Build a plain-text scan report.

    ``type_candidates`` pairs each mutation type with the candidate domains it
    produced (before cross-type de-duplication), so the report can show a
    per-type breakdown. Counts are derived from ``results_by_domain``.
    """
    unique: list[str] = []
    seen: set[str] = set()
    for _, candidates in type_candidates:
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)

    live = [results_by_domain[d] for d in unique if d in results_by_domain and results_by_domain[d].live]
    https_count = sum(1 for r in live if r.https_live)
    http_count = sum(1 for r in live if r.http_live)

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("TYPOSQUATTING SCAN REPORT")
    lines.append("=" * 60)
    lines.append(f"Target:        {target}")
    lines.append(f"Generated:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if elapsed_s is not None:
        lines.append(f"Duration:      {elapsed_s:.1f}s")
    lines.append("")

    lines.append("Scanned domain")
    if target_info is not None:
        resolves = "yes" if target_info.ips else "no"
        status = "online" if target_info.live else "offline / no response"
        lines.append(f"  Status:        {status}")
        lines.append(f"  Resolves DNS:  {resolves}")
        lines.append(f"  IP address:    {target_info.ips[0] if target_info.ips else '-'}")
        if len(target_info.ips) > 1:
            lines.append(f"  Other IPs:     {', '.join(target_info.ips[1:])}")
        lines.append(f"  HTTPS:         {'live' if target_info.https_live else 'dead'}")
        lines.append(f"  HTTP:          {'live' if target_info.http_live else 'dead'}")
        lines.append(f"  Location:      {target_info.location or '-'}")
    else:
        lines.append("  (not checked)")
    lines.append("")
    lines.append("Totals")
    lines.append(f"  Candidates checked:  {len(unique)}")
    lines.append(f"  Live (any):          {len(live)}")
    lines.append(f"  HTTPS live:          {https_count}")
    lines.append(f"  HTTP live:           {http_count}")
    lines.append("")

    lines.append("By mutation type")
    name_width = max((len(mutations.LABELS.get(t, t)) for t, _ in type_candidates), default=4)
    for type_name, candidates in type_candidates:
        type_live = sum(1 for d in candidates if d in results_by_domain and results_by_domain[d].live)
        label = mutations.LABELS.get(type_name, type_name)
        lines.append(f"  {label:<{name_width}}  {len(candidates):>4} candidates  {type_live:>3} live")
    lines.append("")

    if live:
        lines.append("Live domains")
        for r in live:
            ip = r.ips[0] if r.ips else "-"
            schemes = ", ".join(s for s, on in (("HTTPS", r.https_live), ("HTTP", r.http_live)) if on)
            lines.append(f"  - {r.domain}  [{schemes}]  IP:{ip}  {r.location or '-'}")
    else:
        lines.append("Live domains: none found.")
    lines.append("=" * 60)
    return "\n".join(lines)


def default_export_path(target: str, ext: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-." else "_" for c in target)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"results_{safe}_{stamp}.{ext}"


def default_report_path(target: str) -> str:
    return default_export_path(target, "txt").replace("results_", "report_", 1)


def save_report(path: "str | Path", report: str) -> None:
    Path(path).write_text(report + "\n", encoding="utf-8")


def _help_text() -> str:
    """Build the man-page-style help document shown for -h/--help."""
    indent = "    "

    # MUTATION TYPES block, derived from the registry.
    flags_width = max(len(", ".join(t.flags)) for t in mutations.TYPES)
    flags_width = max(flags_width, len("-a, --all"))
    type_lines = [
        f"{indent}{', '.join(t.flags):<{flags_width}}  "
        f"{t.description} ({t.example_base} -> {t.example_variant})"
        for t in mutations.TYPES
    ]
    type_lines.append(f"{indent}{'-a, --all':<{flags_width}}  Run every mutation type")
    types_block = "\n".join(type_lines)

    return f"""\
NAME
{indent}typosquatting - generate typo variants of a domain and check which are live

SYNOPSIS
{indent}typosquat DOMAIN (MUTATION-TYPE... | -a) [OPTIONS]
{indent}typosquat -h | --help

DESCRIPTION
{indent}For a target DOMAIN, generate look-alike variants using one or more
{indent}mutation types, then check which variants are actually live: each
{indent}candidate is resolved via DNS, probed over HTTPS and HTTP, and its
{indent}hosting IP is geolocated. Results print as a summary and an end-of-scan
{indent}report, and can be written to JSON or CSV.

{indent}The tool runs once and exits. A DOMAIN and at least one mutation type
{indent}(or -a) are required; with neither, it prints a usage error.

MUTATION TYPES
{indent}Combine freely; at least one is required (or -a for all).

{types_block}

OPTIONS
{indent}-s, --separate      Summarise each mutation type separately (default: combined)
{indent}--workers N         Check N domains in parallel (default: 20). Each candidate
{indent}{indent}                needs DNS, HTTPS, HTTP and geolocation lookups; more workers
{indent}{indent}                = faster scans but more simultaneous connections. Lower it
{indent}{indent}                (e.g. 5) if you hit timeouts or rate limits; raise it
{indent}{indent}                (e.g. 50) for large -a scans on a fast connection.
{indent}--no-cache          Disable the persistent on-disk cache
{indent}-h, --help          Show this manual and exit

OUTPUT FILES
{indent}Each flag takes an optional PATH. With a PATH, the file is written there.
{indent}Without one, the file is auto-named and saved in the current directory.

{indent}--json [PATH]       Results as JSON      (auto: results_<domain>_<timestamp>.json)
{indent}--csv  [PATH]       Results as CSV       (auto: results_<domain>_<timestamp>.csv)
{indent}--report [PATH]     End-of-scan report   (auto: report_<domain>_<timestamp>.txt)

{indent}typosquat google.com -a --csv                  -> results_google.com_<timestamp>.csv
{indent}typosquat google.com -a --csv C:\scans\g.csv   -> C:\scans\g.csv

EXAMPLES
{indent}typosquat google.com -a
{indent}{indent}Run every mutation type against google.com.

{indent}typosquat google.com -o -tld
{indent}{indent}Only omission and TLD-swap variants.

{indent}typosquat google.com --bitsquatting --json out.json
{indent}{indent}Bitsquatting variants, with results written to out.json.

{indent}typosquat google.com -a --csv
{indent}{indent}All types, CSV auto-named and saved in the current directory.

{indent}typosquat example.com -a -s --report
{indent}{indent}All types, per-type summaries, and a saved report.

EXIT STATUS
{indent}0    Scan completed.
{indent}2    Usage error (missing domain, no mutation type, or unsupported TLD).

FILES
{indent}.typosquatting_cache.json
{indent}{indent}Persistent cache of DNS, HTTP-liveness, and geolocation lookups.

NOTES
{indent}For defensive use: monitoring for look-alike domains that may target a
{indent}brand or its users. The supported TLD list lives in typosquat/parser.py."""


def print_help() -> None:
    print(_help_text())
