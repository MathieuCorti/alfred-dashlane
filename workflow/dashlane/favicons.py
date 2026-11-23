"""Website icons for credentials, downloaded straight from each site.

No third-party favicon service is used: such a service would learn the list
of every site the user has an account on. Each site is asked for its own icon,
like a browser does on a visit. Icons are cached as 64 px PNGs; failures are
retried after a week.
"""

import ipaddress
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from . import config

FETCH_LOCK = "favicons.lock"
FAILED = "failed.json"
CHECKED = "checked"
RETRY_FAILED_AFTER = 7 * 24 * 3600
CHECK_EVERY = 6 * 3600
SIZE = 64
WORKERS = 8
TIMEOUT = 6
MAX_HTML = 1_500_000
MAX_ICON = 1_000_000
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
# Formats sips can't convert.
UNSUPPORTED = (".svg", ".svgz")


def enabled():
    return config.env_bool("favicons", True)


def directory():
    path = config.cache_dir() / "favicons"
    path.mkdir(exist_ok=True)
    return path


def icon_path(domain):
    """The cached icon for a domain, or None."""
    if not domain or not enabled():
        return None
    path = config.cache_dir() / "favicons" / f"{domain}.png"
    return str(path) if path.exists() else None


# --- Finding the icon URL --------------------------------------------------


class _IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attrs = {key.lower(): (value or "") for key, value in attrs}
        rel = attrs.get("rel", "").lower().split()
        href = attrs.get("href", "").strip()
        if not href or "mask-icon" in rel:
            return
        if "apple-touch-icon" in rel or "apple-touch-icon-precomposed" in rel:
            size = 180
        elif "icon" in rel:
            size = 32 if attrs.get("type", "").endswith("png") else 16
        else:
            return
        sizes = attrs.get("sizes", "").lower().split("x")
        if len(sizes) == 2 and sizes[0].isdigit():
            size = int(sizes[0])
        if attrs.get("type", "").startswith("image/svg") or href.lower().split("?")[0].endswith(UNSUPPORTED):
            return
        self.candidates.append((size, href))


def _curl(url, output, max_size):
    """Download url into output. Returns the final URL, or None on failure."""
    result = subprocess.run(
        [
            "/usr/bin/curl",
            "--silent",
            "--location",
            "--fail",
            "--proto", "=https,http",
            "--proto-redir", "=https,http",
            "--max-redirs", "5",
            "--max-time", str(TIMEOUT),
            "--max-filesize", str(max_size),
            "--user-agent", USER_AGENT,
            "--output", output,
            "--write-out", "%{url_effective}",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0 or not os.path.getsize(output):
        return None
    return result.stdout.strip() or url


def _icon_urls(host, workdir):
    """Icon URLs to try for a host, best first."""
    page = os.path.join(workdir, "page.html")
    final = _curl(f"https://{host}/", page, MAX_HTML)
    urls = []
    if final:
        parser = _IconLinks()
        try:
            with open(page, "rb") as handle:
                parser.feed(handle.read(MAX_HTML).decode("utf-8", "replace"))
        except Exception:
            pass
        for _, href in sorted(parser.candidates, key=lambda c: -c[0]):
            url = urljoin(final, href)
            if urlparse(url).scheme in ("http", "https"):
                urls.append(url)
        urls.append(urljoin(final, "/favicon.ico"))
    urls.append(f"https://{host}/favicon.ico")
    return list(dict.fromkeys(urls))


def _convert(source, target, workdir):
    tmp = os.path.join(workdir, "converted.png")
    result = subprocess.run(
        ["/usr/bin/sips", "-s", "format", "png", "-Z", str(SIZE), source, "--out", tmp],
        capture_output=True,
    )
    if result.returncode != 0 or not os.path.exists(tmp) or not os.path.getsize(tmp):
        return False
    os.replace(tmp, target)
    return True


def _hosts_to_try(domain):
    """The domain, then its parents: signin.aws.amazon.com → aws.amazon.com → amazon.com."""
    labels = domain.split(".")
    return [".".join(labels[i:]) for i in range(0, max(1, len(labels) - 1))]


def fetch_one(domain):
    """Download and convert one domain's icon. Returns True on success."""
    target = str(directory() / f"{domain}.png")
    with tempfile.TemporaryDirectory() as workdir:
        for host in _hosts_to_try(domain):
            for index, url in enumerate(_icon_urls(host, workdir)):
                raw = os.path.join(workdir, f"icon{index}")
                if _curl(url, raw, MAX_ICON) and _convert(raw, target, workdir):
                    return True
    return False


# --- Batch fetch -------------------------------------------------------------


def _fetchable(domain):
    if not domain or "." not in domain or domain.endswith((".local", ".localhost", ".internal", ".lan")):
        return False
    try:
        ipaddress.ip_address(domain)
        return False  # Private addresses, routers, NAS...: nothing useful to fetch.
    except ValueError:
        return True


def _load_failed():
    try:
        return json.loads((directory() / FAILED).read_text())
    except (OSError, ValueError):
        return {}


def _save_failed(failed):
    fd, tmp = tempfile.mkstemp(dir=str(directory()), prefix=".failed.", suffix=".tmp")
    with os.fdopen(fd, "w") as handle:
        json.dump(failed, handle)
    os.replace(tmp, directory() / FAILED)


def missing_domains(domains):
    failed = _load_failed()
    now = time.time()
    have = {path.stem for path in directory().glob("*.png")}
    return sorted(
        {
            d
            for d in domains
            if _fetchable(d) and d not in have and now - failed.get(d, 0) >= RETRY_FAILED_AFTER
        }
    )


def fetch_missing():
    """Fetch every missing icon for the cached credentials (run in the background)."""
    from . import cache  # Imported here: cache imports this module.

    if not enabled() or not cache.acquire_lock(name=FETCH_LOCK):
        return
    try:
        (directory() / CHECKED).touch()
        domains = missing_domains(c.get("domain", "") for c in cache.load(cache.CREDENTIALS) or [])
        if not domains:
            return
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = dict(zip(domains, pool.map(_safe_fetch, domains)))
        failed = _load_failed()
        now = time.time()
        for domain, ok in results.items():
            if ok:
                failed.pop(domain, None)
            else:
                failed[domain] = now
        _save_failed(failed)
    finally:
        cache.release_lock(FETCH_LOCK)


def _safe_fetch(domain):
    try:
        return fetch_one(domain)
    except Exception:
        return False


def maybe_spawn_fetch():
    """Look for missing icons now and then, e.g. right after the feature is turned on."""
    try:
        checked = time.time() - (config.cache_dir() / "favicons" / CHECKED).stat().st_mtime
    except OSError:
        checked = None
    if checked is None or checked >= CHECK_EVERY:
        spawn_fetch()


def spawn_fetch():
    """Start fetch_missing() in the background unless it is running or disabled."""
    from . import cache

    if not enabled() or cache.lock_held(FETCH_LOCK):
        return
    try:
        subprocess.Popen(
            [sys.executable, str(config.WORKFLOW_DIR / "fetch_favicons.py")],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(config.WORKFLOW_DIR),
        )
    except OSError:
        pass
