"""Liveness checking for candidate domains.

The public entry point is :func:`check_domains`. For each candidate it
resolves DNS (skipping the rest if nothing resolves), probes HTTPS then HTTP,
and geolocates the primary IP (best effort). Work runs across a thread pool.
A small JSON cache (``{key: [value, expires_at]}``) avoids re-hitting the
network on repeated runs.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import requests

from .parser import normalize_host


@dataclass(frozen=True)
class DomainCheckResult:
    domain: str
    https_live: bool
    http_live: bool
    ips: tuple[str, ...]
    location: str | None

    @property
    def live(self) -> bool:
        return self.https_live or self.http_live


DEFAULT_CACHE_PATH = Path(".typosquatting_cache.json")
DEFAULT_WORKERS = 20
_URL_TTL_LIVE_S = 30 * 60
_URL_TTL_DEAD_S = 2 * 60
_DNS_TTL_S = 60 * 60
_GEO_TTL_S = 30 * 24 * 60 * 60
_GEO_NEGATIVE_TTL_S = 6 * 60 * 60


def _load_cache(path: Path, now: float) -> dict[str, list]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, list) and len(v) == 2 and v[1] > now}


def link_exists(url: str, *, timeout_s: float = 2.0, session: "requests.Session | None" = None) -> bool:
    """Whether a fully-qualified URL (including scheme) responds with < 400."""
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"url must include a scheme (http:// or https://): {url!r}")
    try:
        return (session or requests).head(url, timeout=timeout_s, allow_redirects=True).status_code < 400
    except requests.RequestException:
        return False


def resolve_ips(domain: str) -> tuple[str, ...]:
    """Resolve a host to a de-duplicated tuple of IP addresses."""
    host = normalize_host(domain)
    if not host:
        return ()
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except OSError:
        return ()
    return tuple(dict.fromkeys(info[4][0] for info in infos))


def lookup_ip_location(ip: str, *, timeout_s: float = 2.0, session: "requests.Session | None" = None) -> str | None:
    """Best-effort IP geolocation (City, Region, Country)."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None
    try:
        data = (session or requests).get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,regionName,city"},
            timeout=timeout_s,
        ).json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    parts = [str(data.get(k) or "").strip() for k in ("city", "regionName", "country")]
    return ", ".join(p for p in parts if p) or None


def check_domains(
    domains: list[str],
    *,
    on_progress: Callable[[int, int, str, bool, bool, tuple[str, ...], str | None], None] | None = None,
    include_location: bool = True,
    timeout_s: float = 2.0,
    max_workers: int = DEFAULT_WORKERS,
    cache_path: "str | os.PathLike[str] | None" = DEFAULT_CACHE_PATH,
    cache_enabled: bool = True,
) -> dict[str, DomainCheckResult]:
    """Check candidate domains concurrently; return per-domain results.

    DNS is resolved first and HTTP probing is skipped for domains that do not
    resolve, which is where most of the speed-up comes from.
    """
    now = time.time()
    cache_file = Path(cache_path) if cache_enabled and cache_path is not None else None
    # ponytail: plain dict, GIL-atomic get/set is enough for a CLI; add a lock if it ever grows.
    cache: dict[str, list] = _load_cache(cache_file, now) if cache_file else {}

    def cached(key: str, ttl: Callable[[object], float], compute: Callable[[], object]) -> object:
        entry = cache.get(key)
        if entry and entry[1] > time.time():
            return entry[0]
        value = compute()
        if cache_file:
            cache[key] = [value, time.time() + ttl(value)]
        return value

    lock = threading.Lock()
    total = len(domains)
    done = 0
    session = requests.Session()
    session.headers.setdefault("User-Agent", "TyposquattingChecker/2.0")

    def worker(domain: str) -> DomainCheckResult:
        nonlocal done
        host = normalize_host(domain)
        https_live = http_live = False
        ips: tuple[str, ...] = ()
        location: str | None = None
        if host:
            ips = tuple(cached(f"dns:{host}", lambda _: _DNS_TTL_S, lambda: list(resolve_ips(host))))
            if ips:  # DNS-first filter: only probe hosts that resolve.
                url_ttl = lambda live: _URL_TTL_LIVE_S if live else _URL_TTL_DEAD_S  # noqa: E731
                https_live = cached(f"url:https://{host}", url_ttl, lambda: link_exists(f"https://{host}", timeout_s=timeout_s, session=session))
                http_live = cached(f"url:http://{host}", url_ttl, lambda: link_exists(f"http://{host}", timeout_s=timeout_s, session=session))
                if include_location and (https_live or http_live):
                    location = cached(
                        f"geo:{ips[0]}",
                        lambda loc: _GEO_TTL_S if loc else _GEO_NEGATIVE_TTL_S,
                        lambda: lookup_ip_location(ips[0], timeout_s=timeout_s, session=session),
                    )
        result = DomainCheckResult(domain, bool(https_live), bool(http_live), ips, location)
        if on_progress is not None:
            with lock:
                done += 1
                index = done
            on_progress(index, total, domain, result.https_live, result.http_live, ips, location)
        return result

    results: dict[str, DomainCheckResult] = {}
    try:
        if total:
            with ThreadPoolExecutor(max_workers=max(1, min(max_workers, total))) as pool:
                for result in pool.map(worker, domains):
                    results[result.domain] = result
    finally:
        session.close()

    if cache_file:
        try:
            cache_file.write_text(json.dumps(cache), encoding="utf-8")
        except OSError:
            pass
    return results
