"""Website icons for credentials, downloaded straight from each site.

No third-party favicon service is used: such a service would learn the list
of every site the user has an account on. Each site is asked for its own icon,
like a browser does on a visit. Icons are cached as 64 px PNGs; failures are
retried after a week.
"""

import base64
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
# Bump when fetching improves, so earlier failures are retried right away.
FETCHER_VERSION = 4
RETRY_FAILED_AFTER = 7 * 24 * 3600
CHECK_EVERY = 6 * 3600
SIZE = 64
WORKERS = 8
PAGE_TIMEOUT = 12
ICON_TIMEOUT = 8
MAX_HTML = 1_500_000
MAX_ICON = 1_000_000
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
# Paths many sites serve without declaring them in their HTML.
CONVENTIONAL_PATHS = ("/apple-touch-icon.png", "/favicon.ico", "/favicon.png")


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
    """Collects (size, href) for every <link> icon of a page."""

    def __init__(self):
        super().__init__()
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        attrs = {key.lower(): (value or "") for key, value in attrs}
        rel = attrs.get("rel", "").lower().split()
        href = attrs.get("href", "").strip()
        if not href or "mask-icon" in rel:  # mask-icon: monochrome Safari pinned-tab shape
            return
        is_svg = attrs.get("type", "").startswith("image/svg") or href.lower().split("?")[0].endswith(".svg")
        if "apple-touch-icon" in rel or "apple-touch-icon-precomposed" in rel:
            size = 180
        elif "icon" in rel:
            size = 120 if is_svg else (32 if attrs.get("type", "").endswith("png") else 16)
        else:
            return
        sizes = attrs.get("sizes", "").lower().split("x")
        if len(sizes) == 2 and sizes[0].isdigit():
            size = int(sizes[0])
        self.candidates.append((size, href))


# curl exit codes for TLS/certificate failures, where retrying over http can help.
TLS_ERRORS = {35, 51, 53, 54, 58, 59, 60, 64, 66, 77, 80, 82, 83, 90, 91}


def _curl(url, output, max_size, timeout, accept_errors=False):
    """Download url into output. Returns the final URL, or None on failure."""
    return _run_curl(url, output, max_size, timeout, accept_errors)[1]


CURL_TIMEOUT = 28


def _run_curl(url, output, max_size, timeout, accept_errors=False, partial_ok=False):
    """Download url into output. Returns (curl exit code, final URL or None).

    partial_ok keeps what arrived before a timeout: enough for a page's <head>.

    accept_errors keeps 4xx/5xx bodies: error pages often still declare the icon.
    """
    jar = os.path.join(os.path.dirname(output), "cookies.txt")
    args = [
        "/usr/bin/curl",
        "--silent",
        "--location",
        "--proto", "=https,http",
        "--proto-redir", "=https,http",
        "--max-redirs", "10",
        # Cookies: some sites bounce through a login/consent page that sets one
        # and loop forever without it. The jar is temporary and per domain.
        "--cookie", jar,
        "--cookie-jar", jar,
        "--max-time", str(timeout),
        "--max-filesize", str(max_size),
        "--user-agent", USER_AGENT,
        "--header", "Accept: text/html,application/xhtml+xml,image/*,*/*;q=0.8",
        "--header", "Accept-Language: en-US,en;q=0.9",
        "--output", output,
        "--write-out", "%{url_effective}",
        url,
    ]
    if not accept_errors:
        args.insert(1, "--fail")
    if not os.path.exists(jar):
        open(jar, "w").close()
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    received = os.path.exists(output) and os.path.getsize(output) > 0
    if result.returncode == 0 and received:
        return 0, result.stdout.strip() or url
    if partial_ok and result.returncode == CURL_TIMEOUT and received:
        return CURL_TIMEOUT, result.stdout.strip() or url
    return result.returncode, None


def _origin(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _icon_sources(host, workdir):
    """Icon URLs (or data: URIs) to try for a host, best first."""
    page = os.path.join(workdir, "page.html")
    code, final = _run_curl(f"https://{host}/", page, MAX_HTML, PAGE_TIMEOUT, accept_errors=True, partial_ok=True)
    if not final and code in TLS_ERRORS:
        # Broken or outdated certificate: the icon is public, plain http is fine.
        code, final = _run_curl(f"http://{host}/", page, MAX_HTML, PAGE_TIMEOUT, accept_errors=True, partial_ok=True)
    sources = []
    if final:
        parser = _IconLinks()
        try:
            with open(page, "rb") as handle:
                parser.feed(handle.read(MAX_HTML).decode("utf-8", "replace"))
        except Exception:
            pass
        for _, href in sorted(parser.candidates, key=lambda c: -c[0]):
            if href.startswith("data:image/"):
                sources.append(href)
                continue
            url = urljoin(final, href)
            if urlparse(url).scheme in ("http", "https"):
                sources.append(url)
        sources += [_origin(final) + path for path in CONVENTIONAL_PATHS]
    origins = [f"https://{host}"] + ([f"http://{host}"] if code in TLS_ERRORS else [])
    for origin in origins:
        sources += [origin + path for path in CONVENTIONAL_PATHS]
    return list(dict.fromkeys(sources))


def _save_data_uri(uri, output):
    header, _, payload = uri.partition(",")
    if ";base64" not in header or len(payload) > MAX_ICON * 2:
        return False
    try:
        data = base64.b64decode(payload, validate=False)
    except ValueError:
        return False
    with open(output, "wb") as handle:
        handle.write(data)
    return bool(data)


def _is_svg(path):
    with open(path, "rb") as handle:
        head = handle.read(2048).lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)


def _convert(source, target, workdir):
    """Convert any image (ICO, PNG, JPEG, WebP, SVG...) to a SIZE px PNG at target."""
    if _is_svg(source):
        # sips can't read SVG; Quick Look renders it.
        svg = os.path.join(workdir, "icon.svg")
        os.replace(source, svg)
        subprocess.run(["/usr/bin/qlmanage", "-t", "-s", str(SIZE), "-o", workdir, svg], capture_output=True, timeout=20)
        tmp = svg + ".png"
    else:
        tmp = os.path.join(workdir, "converted.png")
        subprocess.run(["/usr/bin/sips", "-s", "format", "png", "-Z", str(SIZE), source, "--out", tmp], capture_output=True)
    if not os.path.exists(tmp) or not os.path.getsize(tmp):
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
    tried = set()
    with tempfile.TemporaryDirectory() as workdir:
        for host in _hosts_to_try(domain):
            for index, source in enumerate(_icon_sources(host, workdir)):
                if source in tried:
                    continue
                tried.add(source)
                raw = os.path.join(workdir, f"icon{index}")
                if source.startswith("data:"):
                    fetched = _save_data_uri(source, raw)
                else:
                    fetched = _curl(source, raw, MAX_ICON, ICON_TIMEOUT)
                if fetched and _convert(raw, target, workdir):
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
    """Domains whose icon was not found, with when. Reset when the fetcher improves."""
    try:
        data = json.loads((directory() / FAILED).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != FETCHER_VERSION:
        return {}
    return data.get("domains", {})


def _save_failed(failed):
    fd, tmp = tempfile.mkstemp(dir=str(directory()), prefix=".failed.", suffix=".tmp")
    with os.fdopen(fd, "w") as handle:
        json.dump({"version": FETCHER_VERSION, "domains": failed}, handle)
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
    try:
        outdated = json.loads((config.cache_dir() / "favicons" / FAILED).read_text()).get("version") != FETCHER_VERSION
    except (OSError, ValueError, AttributeError):
        outdated = False
    if checked is None or checked >= CHECK_EVERY or outdated:
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
