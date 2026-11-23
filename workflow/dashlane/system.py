"""Clipboard, paste, auto-type and URL opening."""

import json
import subprocess

from . import config

OSASCRIPT = ["/usr/bin/osascript", "-l", "JavaScript"]
PASTEBOARD = str(config.WORKFLOW_DIR / "pasteboard.js")

ACCESSIBILITY_HELP = (
    "Alfred needs Accessibility access to type or paste: "
    "System Settings › Privacy & Security › Accessibility."
)


class PermissionMissing(Exception):
    pass


def _run_jxa(args, stdin):
    try:
        return subprocess.run(
            [*OSASCRIPT, *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip()
        if "not allowed" in detail or "1002" in detail or "-1743" in detail:
            raise PermissionMissing(ACCESSIBILITY_HELP) from None
        raise RuntimeError(detail.splitlines()[-1] if detail else "osascript failed") from None


def copy(text, secret=True):
    """Copy text to the clipboard.

    Secrets stay off Universal Clipboard, are marked concealed/transient so
    clipboard managers skip them, and are cleared after the configured delay
    unless something else was copied. Returns the seconds before clearing (0 = never).
    """
    change_count = _run_jxa([PASTEBOARD, "copy", "1" if secret else "0"], text).strip()
    clear_after = config.clear_clipboard_after() if secret else 0
    if clear_after:
        subprocess.Popen(
            [*OSASCRIPT, PASTEBOARD, "clear", change_count, str(clear_after)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return clear_after


def paste(text, secret=True):
    """Paste text into the frontmost app, then restore the previous clipboard."""
    _run_jxa([PASTEBOARD, "paste", "1" if secret else "0"], text)


def autotype(login, password):
    _run_jxa(
        [str(config.WORKFLOW_DIR / "autotype.js")],
        json.dumps({"login": login, "password": password, "submit": config.autotype_submit()}),
    )


def open_url(url):
    # Callers only pass http(s) URLs (items.web_url), so the argument can't be an option.
    subprocess.run(["/usr/bin/open", url], check=True)


def clears_in(seconds):
    if not seconds:
        return ""
    if seconds < 60:
        return f"clipboard clears in {seconds} s"
    return f"clipboard clears in {seconds // 60} min"
