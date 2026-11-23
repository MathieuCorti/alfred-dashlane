"""Local cache of vault metadata.

Only non-secret fields are cached (title, login, URL, whether 2FA exists...).
Passwords, 2FA secrets and note contents are always read from dcli on demand.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

from . import config, dcli

CREDENTIALS = "credentials.json"
NOTES = "notes.json"
STATE = "state.json"
REFRESH_LOCK = "refresh.lock"
# Bumped by clear(): a refresh that started before it must not save its result.
GENERATION = "generation"

# Bump when the cached fields change, so old caches are rebuilt right away.
CACHE_VERSION = 2
# A lock older than this is considered abandoned (dcli timeouts add up to ~255 s).
LOCK_TTL = 600
# After a failed refresh, wait this long before retrying automatically.
ERROR_RETRY_AFTER = 10


def _path(name):
    return config.cache_dir() / name


def _unlink(name):
    try:
        _path(name).unlink()
    except FileNotFoundError:
        pass


def load(name):
    try:
        with open(_path(name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def save(name, data):
    """Write atomically, readable by the user only. Safe with concurrent writers."""
    directory = config.cache_dir()
    fd, tmp = tempfile.mkstemp(dir=str(directory), prefix=f".{name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        os.replace(tmp, directory / name)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def generation():
    try:
        return _path(GENERATION).read_text()
    except OSError:
        return ""


def clear():
    """Forget the vault (after lock/logout) and invalidate running refreshes."""
    save(GENERATION, repr(time.time()))
    for name in (CREDENTIALS, NOTES, STATE):
        _unlink(name)


def age(name):
    try:
        return time.time() - _path(name).stat().st_mtime
    except FileNotFoundError:
        return None


def record_error(error):
    """Remember a dcli failure so the Script Filters can explain and offer a fix."""
    save(STATE, {"error": error.kind, "message": error.message, "at": time.time()})
    if error.kind in dcli.NEEDS_LOGIN:
        # Don't keep showing a vault the CLI can no longer open.
        _unlink(CREDENTIALS)
        _unlink(NOTES)


# --- Metadata extraction -------------------------------------------------


def domain_of(url):
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def credential_meta(item):
    url = _text(item.get("url"))
    if item.get("useFixedUrl") == "true" and _text(item.get("userSelectedUrl")):
        url = _text(item["userSelectedUrl"])
    if url and "://" not in url:
        url = f"https://{url}"
    domain = domain_of(url)
    email = _text(item.get("email"))
    login = _text(item.get("login"))
    otp_field = "otpSecret" if item.get("otpSecret") else ("otpUrl" if item.get("otpUrl") else "")
    return {
        "id": dcli.bare_id(_text(item.get("id"))),
        "title": _text(item.get("title")) or domain or "Untitled",
        "login": email or login,
        "secondary_login": login if email and login and login != email else "",
        "url": url,
        "domain": domain,
        "otp": otp_field,
        "has_note": bool(_text(item.get("note"))),
        "favorite": item.get("isFavorite") == "true",
        "last_use": _int(item.get("lastUse")),
        "uses": _int(item.get("numberUse")),
    }


def note_meta(item):
    return {
        "id": dcli.bare_id(_text(item.get("id"))),
        "title": _text(item.get("title")) or "Untitled note",
        "secured": item.get("secured") == "true",
        "last_use": _int(item.get("lastUse")),
    }


def _metas(items, build):
    """Build metadata, skipping malformed items instead of failing the whole refresh."""
    metas = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        try:
            metas.append(build(item))
        except (TypeError, ValueError, AttributeError):
            continue
    return metas


# --- Refresh lock --------------------------------------------------------


def _lock_owner():
    try:
        return int(_path(REFRESH_LOCK).read_text().strip() or 0)
    except (OSError, ValueError):
        return 0


def _pid_alive(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock_is_stale():
    lock_age = age(REFRESH_LOCK)
    if lock_age is None:
        return False
    return lock_age > LOCK_TTL or (lock_age > 2 and not _pid_alive(_lock_owner()))


def acquire_lock(wait=0.0):
    """Atomically take the refresh lock. Returns False if it stays busy for `wait` seconds."""
    deadline = time.time() + wait
    while True:
        try:
            fd = os.open(str(_path(REFRESH_LOCK)), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if _lock_is_stale():
                _unlink(REFRESH_LOCK)
                continue
            if time.time() >= deadline:
                return False
            time.sleep(0.25)
            continue
        with os.fdopen(fd, "w") as handle:
            handle.write(str(os.getpid()))
        return True


def release_lock():
    if _lock_owner() == os.getpid():
        _unlink(REFRESH_LOCK)


def refresh_running():
    return age(REFRESH_LOCK) is not None and not _lock_is_stale()


# --- Refresh ---------------------------------------------------------------


def refresh(sync_first=False, wait=0.0):
    """Reload metadata from dcli under the refresh lock.

    Returns (credentials, notes), or None when another refresh holds the lock.
    Any failure is recorded in state.json before being raised.
    """
    if not acquire_lock(wait):
        return None
    try:
        started = generation()
        try:
            dcli.ensure_ready()
            if sync_first:
                dcli.sync()
            credentials = _metas(dcli.list_credentials(), credential_meta)
            notes = _metas(dcli.list_notes(), note_meta)
        except dcli.DcliError as error:
            record_error(error)
            raise
        except Exception as error:
            failure = dcli.DcliError(dcli.FAILED, f"Could not read the vault: {error}")
            record_error(failure)
            raise failure from None
        if generation() != started:
            # The vault was locked or logged out meanwhile: drop this result.
            return None
        save(CREDENTIALS, credentials)
        save(NOTES, notes)
        save(STATE, {"error": None, "at": time.time(), "count": len(credentials), "version": CACHE_VERSION})
        return credentials, notes
    finally:
        release_lock()


def spawn_refresh():
    """Start a background refresh unless one is already running."""
    if refresh_running():
        return
    try:
        subprocess.Popen(
            [sys.executable, str(config.WORKFLOW_DIR / "refresh.py")],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            cwd=str(config.WORKFLOW_DIR),
        )
    except OSError:
        pass


def should_refresh(name):
    """True when the cache is missing, stale or outdated, or a past error may be gone."""
    state = load(STATE) or {}
    if state.get("error"):
        return time.time() - state.get("at", 0) >= ERROR_RETRY_AFTER
    if state.get("version") != CACHE_VERSION:
        return True
    cache_age = age(name)
    return cache_age is None or cache_age >= config.cache_max_age()


def find_credential(item_id):
    item_id = dcli.bare_id(item_id)
    return next((c for c in load(CREDENTIALS) or [] if c.get("id") == item_id), None)


def find_note(item_id):
    item_id = dcli.bare_id(item_id)
    return next((n for n in load(NOTES) or [] if n.get("id") == item_id), None)
