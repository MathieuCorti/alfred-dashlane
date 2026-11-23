"""Script Filter: the fields of one credential (opened with ↩ on a search result).

The credential id comes from the `item_id` variable, set by the Arg and Vars
utility in front of this Script Filter. ↩ copies a field, ⌘↩ pastes it into
the frontmost app.
"""

import os
import sys

from dashlane import alfred, cache, config, dcli

HINT = "↩ copy · ⌘↩ paste"


def field(entry, key, title, subtitle, paste_subtitle, icon, match, shown=None, open_url=False):
    """A field row. `shown` is what ⌘C / Large Type use (never a secret)."""
    shown = shown or entry["title"]
    item = {
        "uid": f"field-{key}",
        "title": title,
        "subtitle": subtitle,
        "arg": entry["id"],
        "match": match,
        "icon": {"path": config.icon(icon)},
        "text": {"copy": shown, "largetype": shown},
        "variables": {"action": f"copy:{key}"},
        "mods": {
            "cmd": {"subtitle": paste_subtitle, "arg": entry["id"], "variables": {"action": f"paste:{key}"}},
        },
    }
    if open_url:
        item["mods"]["alt"] = {"subtitle": f"Open {entry['url']}", "arg": entry["id"], "variables": {"action": "open-url"}}
        item["quicklookurl"] = entry["url"]
    return item


def command(entry, key, title, subtitle, icon, action, match):
    variables = {"action": action}
    return {
        "uid": f"field-{key}",
        "title": title,
        "subtitle": subtitle,
        "arg": entry["id"],
        "match": match,
        "icon": {"path": config.icon(icon)},
        "text": {"copy": entry["title"], "largetype": entry["title"]},
        "variables": variables,
        "mods": {"cmd": {"subtitle": subtitle, "arg": entry["id"], "variables": variables}},
    }


def build(entry):
    name = entry["title"]
    paste = "Paste into the frontmost app"
    rows = []
    if entry.get("login"):
        login = entry["login"]
        rows.append(field(entry, "login", login, f"Login · {HINT}", f"{paste}: login", "field-login", f"login email {login}", shown=login))
    rows.append(field(entry, "password", "Password", f"{name} · {HINT}", f"{paste}: password", "credential", "password"))
    if entry.get("otp"):
        rows.append(field(entry, "otp", "2FA code", f"{name} · {HINT}", f"{paste}: 2FA code", "credential-otp", "2fa otp code totp"))
    if entry.get("url"):
        url = entry["url"]
        rows.append(
            field(entry, "url", url, f"Website · {HINT} · ⌥↩ open", f"{paste}: website", "field-url", f"website url {url}", shown=url, open_url=True)
        )
    if entry.get("secondary_login"):
        login = entry["secondary_login"]
        rows.append(field(entry, "username", login, f"Username · {HINT}", f"{paste}: username", "field-login", f"username {login}", shown=login))
    if entry.get("has_note"):
        rows.append(field(entry, "note", "Note", f"{name} · {HINT}", f"{paste}: note", "note", "note"))
    rows.append(command(entry, "type", "Type login ⇥ password", "Type them into the frontmost app", "field-type", "type", "type autofill fill"))
    rows.append(command(entry, "card", "Show item card", "Login, password, live 2FA code and website", "field-card", "card", "card show details"))
    return rows


def matches(row, words):
    haystack = f"{row['title']} {row['match']}".lower()
    return all(word in haystack for word in words)


def main(query):
    entries, state, refreshing = alfred.prepare(cache.CREDENTIALS)
    if entries is None:
        return alfred.output_unavailable(state, refreshing)
    item_id = dcli.bare_id(os.environ.get("item_id", ""))
    entry = next((e for e in entries if e.get("id") == item_id), None)
    if not entry:
        return alfred.output(
            [alfred.action_item("Item not found", "It may have been deleted. ↩ to sync your vault", "sync", icon="warning")]
        )
    words = query.lower().split()
    rows = [row for row in build(entry) if matches(row, words)]
    if not rows:
        hint = f"{entry['title']}: try login, password, 2fa, website…"
        rows = [alfred.info_item(f"No field matches “{query.strip()}”", hint, icon="search")]
    alfred.output(rows)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
