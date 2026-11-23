"""Thin wrapper around the Dashlane CLI (dcli).

dcli is always run without a TTY and with stdin closed, so any interactive
prompt (email, master password...) fails fast instead of hanging. Failures
are mapped to a DcliError kind the UI can explain.
"""

import json
import os
import re
import subprocess

from . import config

ANSI = re.compile(r"\x1b\[[0-9;]*m")

MISSING = "missing"
LOGGED_OUT = "logged_out"
LOCKED = "locked"
AUTH = "auth"
TIMEOUT = "timeout"
FAILED = "failed"

# Errors that require the user to act in a terminal.
NEEDS_LOGIN = (LOGGED_OUT, LOCKED, AUTH)


class DcliError(Exception):
    def __init__(self, kind, message=""):
        super().__init__(message or kind)
        self.kind = kind
        self.message = message or kind


def _env():
    env = os.environ.copy()
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
    env["FORCE_COLOR"] = "0"
    env["NO_COLOR"] = "1"
    return env


def _classify(stderr, returncode):
    # Only stderr is used: stdout may hold decrypted vault data.
    text = ANSI.sub("", stderr).strip()
    lower = text.lower()
    if "error during authentication" in lower or "invalid device" in lower:
        return DcliError(AUTH, "Your Dashlane session is no longer valid.")
    if "master password" in lower:
        return DcliError(LOCKED, "Your Dashlane vault is locked.")
    if "email address" in lower or "not logged" in lower:
        return DcliError(LOGGED_OUT, "You are not logged in to the Dashlane CLI.")
    lines = [line for line in text.splitlines() if line.strip()]
    message = lines[-1] if lines else f"dcli failed (exit code {returncode})."
    return DcliError(FAILED, re.sub(r"^error:\s*", "", message, flags=re.I)[:300])


def run(args, timeout=30):
    path = config.dcli_path()
    if not path:
        raise DcliError(MISSING, "The Dashlane CLI (dcli) was not found.")
    try:
        proc = subprocess.run(
            [path, *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=_env(),
        )
    except subprocess.TimeoutExpired:
        raise DcliError(TIMEOUT, "The Dashlane CLI did not answer in time.") from None
    except (OSError, UnicodeDecodeError) as error:
        raise DcliError(FAILED, f"Could not run dcli: {error}") from None
    if proc.returncode != 0:
        raise _classify(proc.stderr, proc.returncode)
    return proc.stdout


def status():
    """Return {'logged_in': bool, 'locked': bool}."""
    out = ANSI.sub("", run(["status"], timeout=15))
    fields = {}
    for line in out.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip().lower()
    return {
        "logged_in": fields.get("logged in") == "yes",
        "locked": fields.get("locked") == "yes",
    }


def ensure_ready():
    state = status()
    if not state["logged_in"]:
        raise DcliError(LOGGED_OUT, "You are not logged in to the Dashlane CLI.")
    if state["locked"]:
        raise DcliError(LOCKED, "Your Dashlane vault is locked.")


def _list(command):
    # With -o json, dcli prints "[]" (exit code 0) when there is no item.
    out = run([command, "-o", "json"], timeout=120).strip()
    try:
        items = json.loads(out) if out else []
    except ValueError:
        # from None: the decode error may quote decrypted vault data.
        raise DcliError(FAILED, f"dcli {command} returned unexpected output.") from None
    if not isinstance(items, list):
        raise DcliError(FAILED, f"dcli {command} returned unexpected output.")
    return items


def list_credentials():
    return _list("password")


def list_notes():
    return _list("note")


def bare_id(item_id):
    return item_id.strip().strip("{}")


def read(item_id, field, transform=None):
    path = f"dl://{bare_id(item_id)}/{field}"
    if transform:
        path += f"?{transform}"
    return run(["read", path]).rstrip("\n")


def read_otp(item_id, otp_field):
    """Return (code, seconds_remaining) for a credential with 2FA."""
    transform = "otp_uri+expiry" if otp_field == "otpUrl" else "otp+expiry"
    code, _, remaining = read(item_id, otp_field, transform).strip().partition(" ")
    try:
        seconds = int(remaining)
    except ValueError:
        seconds = 30
    return code, seconds


def sync():
    run(["sync"], timeout=120)


def lock():
    run(["lock"], timeout=15)


def terminal_command(kind):
    """Shell command the user runs in a terminal to fix a login problem."""
    dcli = config.dcli_path() or "dcli"
    quoted = "'" + dcli.replace("'", "'\\''") + "'"
    if kind == AUTH:
        # The local session is broken: log out, then log in again.
        return f"{quoted} logout && {quoted} sync"
    return f"{quoted} sync"
