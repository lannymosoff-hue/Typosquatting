# Typosquatting Checker

Generates typo variants of a domain and checks which ones are actually live.
For each candidate it resolves DNS, probes HTTPS/HTTP, and geolocates the
hosting IP, so you can quickly see which look-alike domains are registered and
serving content.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/lannymosoff-hue/Typosquatting.git
cd Typosquatting
python -m pip install .
typosquat --help
```

If `typosquat` is reported as "not found", pip's scripts folder isn't on your
PATH. pip prints that folder in a warning during install — add it to PATH, or
run the tool as `python -m typosquat ...` instead (works from any folder once
installed).

## Usage

```
typosquat DOMAIN (MUTATION-TYPE... | -a) [OPTIONS]
```

The tool runs once and exits. A domain and at least one mutation type (or `-a`)
are required.

```bash
typosquat google.com -a                        # every mutation type
typosquat google.com -o -tld                   # omission + TLD swap only
typosquat google.com --bitsquatting --json results.json
typosquat google.com -a --csv --report         # auto-named CSV + report in the current folder
typosquat google.com -a -s --workers 5         # per-type summaries, gentler on the network
typosquat --help                               # full manual
```

### Mutation types

Combine freely; at least one is required (or `-a` for all).

| Flag | Type | Example (`google`) |
|------|------|--------------------|
| `-o`, `--omission` | Drop one character | `gogle` |
| `-r`, `--replacement` | Replace one character (QWERTY adjacency) | `googke` |
| `-t`, `--transposition` | Swap adjacent characters | `googel` |
| `--insertion` | Insert an adjacent key | `googsle` |
| `--repetition` | Double a character | `gooogle` |
| `--vowel-swap` | Swap vowels | `gaogle` |
| `--hyphenation` | Insert a hyphen | `goo-gle` |
| `--addition` | Append a character | `googlea` |
| `--bitsquatting` | Flip one bit per character | `eoogle` |
| `-tld`, `--tld-swap` | Swap the TLD | `google.net` |
| `-a`, `--all` | All of the above | |

### Options

| Flag | Description |
|------|-------------|
| `-s`, `--separate` | Summarise each mutation type separately (default: combined) |
| `--workers N` | Domains checked in parallel (default: 20). Lower it (e.g. 5) on timeouts or rate limits; raise it (e.g. 50) for large `-a` scans |
| `--no-cache` | Disable the persistent on-disk cache |
| `-h`, `--help` | Show the full manual and exit |

### Output files

Each flag takes an optional `PATH`. With a path, the file is written there;
without one, it is auto-named and saved in the current folder.

| Flag | Contents | Auto-name |
|------|----------|-----------|
| `--json [PATH]` | Per-domain results as JSON | `results_<domain>_<timestamp>.json` |
| `--csv [PATH]` | Per-domain results as CSV | `results_<domain>_<timestamp>.csv` |
| `--report [PATH]` | End-of-scan text report | `report_<domain>_<timestamp>.txt` |

### Exit status

| Code | Meaning |
|------|---------|
| `0` | Scan completed |
| `2` | Usage error (missing domain, no mutation type, or unsupported TLD) |

## How it works

- **typosquat/mutations.py** — the variant generators and their registry (`ALL_TYPES`, `generate`).
- **typosquat/parser.py** — splits a domain into SLD/TLD against a configurable TLD list.
- **typosquat/checker.py** — concurrent liveness checking. DNS is resolved first and HTTP
  probing is skipped for domains that do not resolve. DNS, liveness and
  geolocation results are cached in `.typosquatting_cache.json` (in the
  current folder) with per-category TTLs.
- **typosquat/output.py** — console rendering, the `--help` manual, JSON/CSV/report export.
- **typosquat/main.py** — argument parsing and control flow (`main()` returns the exit code).

## Notes

This tool is for defensive use: monitoring for look-alike domains that may
target your brand or users. The supported TLD list lives in `typosquat/parser.py`.

