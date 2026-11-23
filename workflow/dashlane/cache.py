"""Local cache of vault metadata.

Only non-secret fields are cached (title, login, URL, whether 2FA exists...).
Passwords, 2FA secrets and note contents are always read from dcli on demand.
"""

import json
import os
import subprocess
import sys
import time
from urllib.parse import urlparse

from . import config, dcli

CREDENTIALS = "credentials.json"
NOTES = "notes.json"
STATE = "state.json"
REFRESH_LOCK = "refresh.lock"

# A refresh holding the lock for longer than this is considered dead.
LOCK_TTL = 180
# After a failed refresh, wait this long before retrying automatically.
ERROR_RETRY_AFTER = 10


def _path(name):
    return config.cache_dir() / name


def load(name):
    try:
        with open(_path(name), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def save(name, data):
    path = _path(name)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(tmp, path)


def clear():
    for name in (CREDENTIALS, NOTES, STATE):
        try:
            _path(name).unlink()
        except FileNotFoundError:
            pass


def age(name):
    try:
        return time.time() - _path(name).stat().st_mtime
    except FileNotFoundError:
        return None


# --- Metadata extraction -------------------------------------------------


def domain_of(url):
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def credential_meta(item):
    url = item.get("url") or ""
    if item.get("useFixedUrl") == "true" and item.get("userSelectedUrl"):
        url = item["userSelectedUrl"]
    if url and "://" not in url:
        url = f"https://{url}"
    domain = domain_of(url)
    email = (item.get("email") or "").strip()
    login = (item.get("login") or "").strip()
    otp_field = "otpSecret" if item.get("otpSecret") else ("otpUrl" if item.get("otpUrl") else "")
    return {
        "id": dcli.bare_id(item.get("id", "")),
        "title": (item.get("title") or "").strip() or domain or "Untitled",
        "login": email or login,
        "secondary_login": login if email and login and login != email else "",
        "url": url,
        "domain": domain,
        "otp": otp_field,
        "has_note": bool((item.get("note") or "").strip()),
        "favorite": item.get("isFavorite") == "true",
        "last_use": _int(item.get("lastUse")),
        "uses": _int(item.get("numberUse")),
    }


def note_meta(item):
    return {
        "id": dcli.bare_id(item.get("id", "")),
        "title": (item.get("title") or "").strip() or "Untitled note",
        "secured": item.get("secured") == "true",
        "last_use": _int(item.get("lastUse")),
    }


# --- Refresh ---------------------------------------------------------------


def refresh(sync_first=False):
    """Reload metadata from dcli. Records the outcome in state.json."""
    try:
        dcli.ensure_ready()
        if sync_first:
            dcli.sync()
        credentials = [credential_meta(c) for c in dcli.list_credentials()]
        notes = [note_meta(n) for n in dcli.list_notes()]
    except dcli.DcliError as error:
        save(STATE, {"error": error.kind, "message": error.message, "at": time.time()})
        if error.kind in dcli.NEEDS_LOGIN:
            # Don't keep showing a vault the CLI can no longer open.
            for name in (CREDENTIALS, NOTES):
                try:
                    _path(name).unlink()
                except FileNotFoundError:
                    pass
        raise
    save(CREDENTIALS, credentials)
    save(NOTES, notes)
    save(STATE, {"error": None, "at": time.time(), "count": len(credentials)})
    return credentials, notes


def refresh_running():
    lock_age = age(REFRESH_LOCK)
    return lock_age is not None and lock_age < LOCK_TTL


def spawn_refresh():
    """Start a background refresh unless one is already running."""
    if refresh_running():
        return
    _path(REFRESH_LOCK).touch()
    subprocess.Popen(
        [sys.executable, str(config.WORKFLOW_DIR / "refresh.py")],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(config.WORKFLOW_DIR),
    )


def release_refresh_lock():
    try:
        _path(REFRESH_LOCK).unlink()
    except FileNotFoundError:
        pass


def should_refresh(name):
    """True when the cache is missing/stale and no recent error blocks a retry."""
    cache_age = age(name)
    if cache_age is not None and cache_age < config.cache_max_age():
        return False
    state = load(STATE) or {}
    if state.get("error") and time.time() - state.get("at", 0) < ERROR_RETRY_AFTER:
        return False
    return True


def find_credential(item_id):
    item_id = dcli.bare_id(item_id)
    return next((c for c in load(CREDENTIALS) or [] if c["id"] == item_id), None)


def find_note(item_id):
    item_id = dcli.bare_id(item_id)
    return next((n for n in load(NOTES) or [] if n["id"] == item_id), None)
