"""Run Script: perform the action chosen in Alfred or in an item card.

Input: the item id (or an error kind for "login") as argv[1], and the action
in the `action` variable. Output: Alfred JSON whose `next` variable tells the
workflow what to do afterwards ("notify" or "terminal") and whose arg is the
notification text or the terminal command.
"""

import json
import os
import sys

from dashlane import cache, dcli, system


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


def copied(what, entry_title, seconds):
    suffix = system.clears_in(seconds)
    return done(f"{entry_title}{' · ' + suffix if suffix else ''}", f"{what} copied")


def main(action, arg):
    if action == "copy-password":
        entry = credential(arg)
        seconds = system.copy(dcli.read(arg, "password"))
        return copied("Password", entry["title"], seconds)

    if action == "copy-login":
        entry = credential(arg)
        system.copy(entry["login"], secret=False)
        return done(entry["title"], f"Login copied: {entry['login']}")

    if action == "copy-otp":
        entry = credential(arg)
        if not entry["otp"]:
            return done(entry["title"], "This item has no 2FA code")
        code, remaining = dcli.read_otp(arg, entry["otp"])
        system.copy(code)
        return done(f"{entry['title']} · valid for {remaining} s", "2FA code copied")

    if action == "type":
        entry = credential(arg)
        system.autotype(entry["login"], dcli.read(arg, "password"))
        return done()

    if action == "open-url":
        url = arg if "://" in arg else credential(arg)["url"]
        if url:
            system.open_url(url)
        return done()

    if action == "copy-note":
        entry = cache.find_note(arg) or {"title": "Note"}
        seconds = system.copy(dcli.read(arg, "content"))
        return copied("Note", entry["title"], seconds)

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
