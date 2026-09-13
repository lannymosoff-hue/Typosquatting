"""Typo-variant generators for a second-level domain (SLD).

Each public ``generate_*`` function takes a bare SLD (e.g. ``"google"``) and
returns a deterministic, de-duplicated list of variant SLDs that never includes
the original. ``build_domains`` appends a TLD to turn variants into full
domains. ``generate_tld_swaps`` is the one exception: it varies the TLD instead
of the SLD.

``TYPES`` is the registry the rest of the program iterates over.
"""

from __future__ import annotations

import string
from collections.abc import Callable
from dataclasses import dataclass


_QWERTY_ADJACENCY: dict[str, str] = {
    "a": "qwsz",
    "b": "vghn",
    "c": "xdfv",
    "d": "ersfxc",
    "e": "wsdr",
    "f": "rtgdvc",
    "g": "tyfhvb",
    "h": "yugjbn",
    "i": "ujko",
    "j": "uikhmn",
    "k": "ijolm",
    "l": "kop",
    "m": "njk",
    "n": "bhjm",
    "o": "iklp",
    "p": "ol",
    "q": "wa",
    "r": "edft",
    "s": "wedxza",
    "t": "rfgy",
    "u": "yhji",
    "v": "cfgb",
    "w": "qase",
    "x": "zsdc",
    "y": "tghu",
    "z": "asx",
    "0": "9",
    "1": "2",
    "2": "13",
    "3": "24",
    "4": "35",
    "5": "46",
    "6": "57",
    "7": "68",
    "8": "79",
    "9": "80",
    "-": "0=",
}

_VOWELS = "aeiou"
# Characters allowed in a DNS label.
_LABEL_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


def _clean(sld: str) -> str:
    return sld.strip().lower()


def _dedup(variants: list[str], *, original: str) -> list[str]:
    """Preserve order, drop duplicates and any copy of the original."""
    return list(dict.fromkeys(v for v in variants if v and v != original))


def generate_omission(sld: str) -> list[str]:
    """Remove exactly one character per variant ("google" -> "gogle", ...)."""
    text = _clean(sld)
    if len(text) < 2:
        return []
    return _dedup([text[:i] + text[i + 1:] for i in range(len(text))], original=text)


def generate_replacement(sld: str) -> list[str]:
    """Replace one character with a QWERTY-adjacent key, deterministically."""
    text = _clean(sld)
    if not text:
        return []
    variants: list[str] = []
    for i, char in enumerate(text):
        for neighbor in _QWERTY_ADJACENCY.get(char, ""):
            variants.append(text[:i] + neighbor + text[i + 1:])
    return sorted(_dedup(variants, original=text))


def generate_transposition(sld: str) -> list[str]:
    """Swap each adjacent pair of (differing) characters."""
    text = _clean(sld)
    if len(text) < 2:
        return []
    variants: list[str] = []
    for i in range(len(text) - 1):
        if text[i] == text[i + 1]:
            continue
        variants.append(text[:i] + text[i + 1] + text[i] + text[i + 2:])
    return _dedup(variants, original=text)


def generate_insertion(sld: str) -> list[str]:
    """Insert a QWERTY-adjacent character next to each existing character."""
    text = _clean(sld)
    if not text:
        return []
    variants: list[str] = []
    for i, char in enumerate(text):
        for neighbor in _QWERTY_ADJACENCY.get(char, ""):
            if neighbor not in _LABEL_CHARS:
                continue
            variants.append(text[:i] + neighbor + text[i:])
            variants.append(text[:i + 1] + neighbor + text[i + 1:])
    return sorted(_dedup(variants, original=text))


def generate_repetition(sld: str) -> list[str]:
    """Double each character once ("google" -> "ggoogle", "googgle", ...)."""
    text = _clean(sld)
    if not text:
        return []
    return _dedup([text[:i + 1] + text[i] + text[i + 1:] for i in range(len(text))], original=text)


def generate_vowel_swap(sld: str) -> list[str]:
    """Swap each vowel for every other vowel."""
    text = _clean(sld)
    if not text:
        return []
    variants: list[str] = []
    for i, char in enumerate(text):
        if char not in _VOWELS:
            continue
        for vowel in _VOWELS:
            if vowel != char:
                variants.append(text[:i] + vowel + text[i + 1:])
    return sorted(_dedup(variants, original=text))


def generate_hyphenation(sld: str) -> list[str]:
    """Insert a single hyphen between adjacent characters."""
    text = _clean(sld)
    if len(text) < 2:
        return []
    variants = [
        text[:i] + "-" + text[i:]
        for i in range(1, len(text))
        if text[i - 1] != "-" and text[i] != "-"
    ]
    return _dedup(variants, original=text)


def generate_addition(sld: str) -> list[str]:
    """Append a single a-z character to the end."""
    text = _clean(sld)
    if not text:
        return []
    return _dedup([text + c for c in string.ascii_lowercase], original=text)


def generate_bitsquatting(sld: str) -> list[str]:
    """Flip one bit of each character, keeping only valid DNS-label results."""
    text = _clean(sld)
    if not text:
        return []
    variants: list[str] = []
    for i, char in enumerate(text):
        for bit in range(8):
            flipped = chr(ord(char) ^ (1 << bit))
            if flipped in _LABEL_CHARS:
                variants.append(text[:i] + flipped + text[i + 1:])
    return sorted(_dedup(variants, original=text))


def generate_tld_swaps(sld: str, current_tld: str, allowed_tlds: list[str]) -> list[str]:
    """Full domains that keep the SLD but swap to every other allowed TLD."""
    return [f"{sld}{tld}" for tld in allowed_tlds if tld != current_tld]


def build_domains(sld_variants: list[str], tld: str) -> list[str]:
    """Append ``tld`` (normalised with a leading dot) to each SLD variant."""
    value = tld.strip().lower()
    if not value:
        return []
    if not value.startswith("."):
        value = f".{value}"
    return [f"{variant}{value}" for variant in sld_variants if variant]


# --------------------------------------------------------------------------- #
# Registry — the single source of truth for every mutation type.
#
# Add or change a mutation type *here only*: the CLI flags (main.py), the
# man-page help (output.py), and the README all derive their data from this
# table via the helpers below. ``generator`` is ``None`` for
# ``tld_swap``, which varies the TLD instead of the SLD and is special-cased in
# :func:`generate`.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class MutationType:
    name: str  # canonical key, also the argparse destination
    label: str  # human-readable label
    flags: tuple[str, ...]  # CLI option strings, e.g. ("-o", "--omission")
    description: str  # short imperative phrase for help text
    example_base: str  # input shown in examples, e.g. "google"
    example_variant: str  # resulting variant, e.g. "gogle"
    generator: "Callable[[str], list[str]] | None"  # None => tld_swap


TYPES: list[MutationType] = [
    MutationType("omission", "Omission", ("-o", "--omission"),
                 "Drop one character", "google", "gogle", generate_omission),
    MutationType("replacement", "Replacement", ("-r", "--replacement"),
                 "Replace one character (QWERTY adjacency)", "google", "googke", generate_replacement),
    MutationType("transposition", "Transposition", ("-t", "--transposition"),
                 "Swap adjacent characters", "google", "googel", generate_transposition),
    MutationType("insertion", "Insertion", ("--insertion",),
                 "Insert an adjacent key", "google", "googsle", generate_insertion),
    MutationType("repetition", "Repetition", ("--repetition",),
                 "Double a character", "google", "gooogle", generate_repetition),
    MutationType("vowel_swap", "Vowel swap", ("--vowel-swap",),
                 "Swap vowels", "google", "gaogle", generate_vowel_swap),
    MutationType("hyphenation", "Hyphenation", ("--hyphenation",),
                 "Insert a hyphen", "google", "goo-gle", generate_hyphenation),
    MutationType("addition", "Addition", ("--addition",),
                 "Append a character", "google", "googlea", generate_addition),
    MutationType("bitsquatting", "Bitsquatting", ("--bitsquatting",),
                 "Flip one bit per character", "google", "eoogle", generate_bitsquatting),
    MutationType("tld_swap", "TLD swap", ("-tld", "--tld-swap"),
                 "Swap the TLD", "google.com", "google.net", None),
]

LABELS: dict[str, str] = {t.name: t.label for t in TYPES}
ALL_TYPES: list[str] = [t.name for t in TYPES]


def generate(type_name: str, sld: str, tld: str, allowed_tlds: list[str]) -> list[str]:
    """Full domain candidates for one mutation type; unknown names yield []."""
    if type_name == "tld_swap":
        return generate_tld_swaps(sld, tld, allowed_tlds)
    mutation = next((t for t in TYPES if t.name == type_name), None)
    return build_domains(mutation.generator(sld), tld) if mutation and mutation.generator else []
