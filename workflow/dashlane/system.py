"""Clipboard, auto-type and URL opening."""

import json
import subprocess

from . import config

OSASCRIPT = ["/usr/bin/osascript", "-l", "JavaScript"]


def copy(text, secret=True):
    """Copy text to the clipboard.

    Secrets are marked concealed/transient so clipboard managers skip them, and
    are cleared after the configured delay unless something else was copied.
    Returns the number of seconds before clearing (0 = never).
    """
    result = subprocess.run(
        [*OSASCRIPT, str(config.WORKFLOW_DIR / "pasteboard.js"), "copy", "1" if secret else "0"],
        input=text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    clear_after = config.clear_clipboard_after() if secret else 0
    if clear_after:
        subprocess.Popen(
            [
                *OSASCRIPT,
                str(config.WORKFLOW_DIR / "pasteboard.js"),
                "clear",
                result.stdout.strip(),
                str(clear_after),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    return clear_after


def autotype(login, password):
    subprocess.run(
        [*OSASCRIPT, str(config.WORKFLOW_DIR / "autotype.js")],
        input=json.dumps(
            {"login": login, "password": password, "submit": config.autotype_submit()}
        ),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )


def open_url(url):
    subprocess.run(["/usr/bin/open", url], check=True)


def clears_in(seconds):
    if not seconds:
        return ""
    if seconds < 60:
        return f"clipboard clears in {seconds} s"
    minutes = seconds // 60
    return f"clipboard clears in {minutes} min"
