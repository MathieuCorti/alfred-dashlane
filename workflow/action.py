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

from dashlane import cache, dcli, items, system, usage


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


def field_action(mode, field, item_id):
    entry = items.credential(item_id)
    value, secret, detail = items.field_value(entry, field)
    name = items.FIELD_NAMES[field]
    if not value:
        return done(entry["title"], f"This item has no {name.lower()}")
    if mode == "paste":
        try:
            system.paste(value, secret=secret)
        except system.PermissionMissing as error:
            seconds = system.copy(value, secret=secret)
            suffix = f" · {system.clears_in(seconds)}" if secret and seconds else ""
            return done(f"{error}{suffix}", f"{name} copied instead of pasted")
        return done()
    seconds = system.copy(value, secret=secret)
    details = [entry["title"], detail, system.clears_in(seconds) if secret else ""]
    return done(" · ".join(part for part in details if part), f"{name} copied")


ITEM_ACTIONS = ("copy:", "paste:", "type", "open-url", "copy-note")


def main(action, arg):
    if action.startswith(ITEM_ACTIONS) and "://" not in arg:
        usage.record(arg)
    mode, _, field = action.partition(":")
    if mode in ("copy", "paste") and field in items.FIELD_NAMES:
        return field_action(mode, field, arg)

    if action == "type":
        entry = items.credential(arg)
        system.autotype(entry["login"], dcli.read(arg, "password"))
        return done()

    if action == "open-url":
        url = items.web_url(arg if "://" in arg else items.credential(arg)["url"])
        if not url:
            return done("Only http and https addresses are opened.", "Not a web address")
        system.open_url(url)
        return done()

    if action == "copy-note":
        entry = cache.find_note(arg) or {"title": "Note"}
        seconds = system.copy(dcli.read(arg, "content"))
        details = [entry["title"], system.clears_in(seconds)]
        return done(" · ".join(part for part in details if part), "Note copied")

    if action == "sync":
        dcli.sync()
        result = cache.refresh(wait=150)
        if result is None:
            return done("Your vault was synced. The item list is still being reloaded.", "Vault synced")
        credentials, notes = result
        return done(f"{len(credentials)} passwords · {len(notes)} notes", "Vault synced")

    if action == "lock":
        dcli.lock()
        cache.clear()
        cache.record_error(dcli.DcliError(dcli.LOCKED, "Your Dashlane vault is locked."))
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
        if error.kind in dcli.NEEDS_LOGIN or error.kind == dcli.MISSING:
            cache.record_error(error)
        done(error.message, "Dashlane error")
    except system.PermissionMissing as error:
        done(str(error), "Dashlane can't type")
    except Exception as error:  # Surface anything unexpected instead of failing silently.
        done(str(error), "Dashlane error")
