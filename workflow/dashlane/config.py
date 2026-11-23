"""Workflow configuration, read from Alfred's environment variables."""

import os
import shutil
from pathlib import Path

BUNDLE_ID = "com.mathieucorti.alfred.dashlane"
WORKFLOW_DIR = Path(__file__).resolve().parent.parent
ICONS_DIR = WORKFLOW_DIR / "icons"

DCLI_CANDIDATES = ("/opt/homebrew/bin/dcli", "/usr/local/bin/dcli")


def env(name, default=""):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_int(name, default):
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def env_bool(name, default=False):
    value = env(name, "")
    if value == "":
        return default
    return value.lower() in ("1", "true", "yes")


def cache_dir():
    # Alfred UI scripts don't get alfred_workflow_cache, so fall back to the
    # path Alfred uses for this bundle id.
    path = Path(
        env(
            "alfred_workflow_cache",
            str(
                Path.home()
                / "Library/Caches/com.runningwithcrayons.Alfred/Workflow Data"
                / BUNDLE_ID
            ),
        )
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def clear_clipboard_after():
    """Seconds before a copied secret is wiped from the clipboard (0 = never)."""
    return max(0, env_int("clear_clipboard_after", 30))


def cache_max_age():
    """Seconds before the cached item list is refreshed in the background."""
    return max(1, env_int("cache_max_age", 60)) * 60


def autotype_submit():
    return env_bool("autotype_submit", False)


def dcli_path():
    configured = os.path.expanduser(env("dcli_path"))
    if configured:
        return configured if os.access(configured, os.X_OK) else None
    for candidate in DCLI_CANDIDATES:
        if os.access(candidate, os.X_OK):
            return candidate
    return shutil.which("dcli")


def icon(name):
    return str(ICONS_DIR / f"{name}.png")
