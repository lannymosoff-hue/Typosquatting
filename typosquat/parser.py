from __future__ import annotations

from urllib.parse import urlparse


TLD_LIST = [
    ".com", ".net", ".org", ".info", ".biz", ".xyz", ".top", ".club",
    ".online", ".site", ".store", ".shop", ".app", ".dev", ".ai", ".co",
    ".io", ".us", ".ca", ".uk", ".de", ".fr", ".jp", ".cn", ".in", ".br",
    ".ru", ".au", ".co.uk", ".org.uk", ".gov.uk", ".ac.uk", ".com.au",
    ".net.au", ".org.au", ".edu.au", ".gov.au", ".co.nz", ".org.nz",
    ".govt.nz", ".ac.nz", ".com.br", ".net.br", ".org.br", ".gov.br",
    ".co.in", ".net.in", ".org.in", ".gov.in", ".com.cn", ".net.cn",
    ".org.cn", ".gov.cn", ".com.jp", ".co.jp", ".ne.jp", ".or.jp",
    ".go.jp", ".ac.jp", ".com.ru", ".net.ru", ".org.ru", ".co.za",
    ".org.za", ".gov.za",
]


def normalize_host(text: str) -> str | None:
    """Bare lowercase host from a domain or URL; None if nothing is left."""
    text = text.strip()
    parsed = urlparse(text if "://" in text else f"//{text}")
    host = (parsed.netloc or parsed.path).split("/")[0].split(":")[0].strip().lower().rstrip(".")
    return host or None


def split_sld_tld(domain: str, allowed_tlds: list[str]) -> tuple["str | None", "str | None", "str | None"]:
    """Parse a domain string into (sld, tld, host).

    On an invalid domain or unsupported TLD returns (None, None, host) so
    callers can show a helpful error message.
    """
    host = normalize_host(domain)
    if not host:
        return None, None, None
    tld = next((t for t in sorted(allowed_tlds, key=len, reverse=True) if host.endswith(t)), None)
    if tld is None:
        return None, None, host
    sld = host[: -len(tld)].rstrip(".").split(".")[-1]
    return (sld, tld, host) if sld else (None, None, host)


def extract_tld_suffix(host: str) -> str:
    """Best-effort extract the TLD portion from a raw host string for errors."""
    parts = host.rsplit(".", 1)
    return f".{parts[-1]}" if len(parts) == 2 else host
