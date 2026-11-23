"""Run Script: perform the action chosen in Alfred or in an item card.

Input: the item id (or an error kind for "login") as argv[1], and the action
in the `action` variable. Field actions are "copy:<field>" or "paste:<field>".
Output: Alfred JSON whose `next` variable tells the workflow what to do
afterwards ("notify" or "terminal") and whose arg is the notification text or
the terminal command.
"""

import json
import os
import sys

from dashlane import cache, dcli, system

FIELD_NAMES = {
    "login": "Login",
    "username": "Username",
    "password": "Password",
    "otp": "2FA code",
    "url": "Website",
    "note": "Note",
}


def done(text="", title="Dashlane", next_step="notify"):
    sys.stdout.write(
        json.dumps(
            {
                "alfredworkflow": {
                    "arg": text,
                    "variables": {"next": next_step if text else "", "notify_title": title},
                }
            }
        )
    )


def credential(item_id):
    entry = cache.find_credential(item_id)
    if not entry:
        raise dcli.DcliError(dcli.FAILED, "Item not found. Try “sync”.")
    return entry


def field_value(entry, field):
    """Return (value, is_secret, extra notification text) for a credential field."""
    if field == "login":
        return entry["login"], False, ""
    if field == "username":
        return entry.get("secondary_login", ""), False, ""
    if field == "url":
        return entry["url"], False, ""
    if field == "password":
        return dcli.read(entry["id"], "password"), True, ""
    if field == "note":
        return dcli.read(entry["id"], "note"), True, ""
    if field == "otp":
        if not entry["otp"]:
            raise dcli.DcliError(dcli.FAILED, "This item has no 2FA code.")
        code, remaining = dcli.read_otp(entry["id"], entry["otp"])
        return code, True, f"valid for {remaining} s"
    raise dcli.DcliError(dcli.FAILED, f"Unknown field: {field}")


def field_action(mode, field, item_id):
    entry = credential(item_id)
    value, secret, extra = field_value(entry, field)
    if not value:
        return done(entry["title"], f"No {FIELD_NAMES[field].lower()} for this item")
    if mode == "paste":
        system.paste(value, secret=secret)
        return done()
    seconds = system.copy(value, secret=secret)
    details = [entry["title"], extra, system.clears_in(seconds) if secret else ""]
    return done(" · ".join(part for part in details if part), f"{FIELD_NAMES[field]} copied")


def main(action, arg):
    mode, _, field = action.partition(":")
    if mode in ("copy", "paste") and field in FIELD_NAMES:
        return field_action(mode, field, arg)

    if action == "type":
        entry = credential(arg)
        system.autotype(entry["login"], dcli.read(arg, "password"))
        return done()

    if action == "open-url":
        url = arg if "://" in arg else credential(arg)["url"]
        if url:
            system.open_url(url)
        return done()

    if action in ("copy-note", "paste-note"):
        entry = cache.find_note(arg) or {"title": "Note"}
        content = dcli.read(arg, "content")
        if action == "paste-note":
            system.paste(content)
            return done()
        seconds = system.copy(content)
        suffix = system.clears_in(seconds)
        return done(f"{entry['title']}{' · ' + suffix if suffix else ''}", "Note copied")

    if action == "sync":
        dcli.sync()
        credentials, notes = cache.refresh()
        return done(f"{len(credentials)} passwords · {len(notes)} notes", "Vault synced")

    if action == "lock":
        dcli.lock()
        cache.clear()
        return done("Your master password will be asked to unlock it", "Vault locked")

    if action == "login":
        # Forget the error so the next search retries right away.
        cache.clear()
        return done(dcli.terminal_command(arg), next_step="terminal")

    return done()


if __name__ == "__main__":
    action = os.environ.get("action", "")
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        main(action, arg)
    except dcli.DcliError as error:
        if error.kind in dcli.NEEDS_LOGIN:
            cache.save(cache.STATE, {"error": error.kind, "message": error.message, "at": 0})
        done(error.message, "Dashlane error")
    except Exception as error:  # Surface anything unexpected instead of failing silently.
        done(str(error), "Dashlane error")
