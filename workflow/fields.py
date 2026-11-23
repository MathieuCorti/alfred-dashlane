"""Script Filter: the fields of one credential (opened with ↩ on a search result).

The credential id comes from the `item_id` variable. ↩ copies a field, ⌘↩
pastes it into the frontmost app. Alfred filters the list as you type.
"""

import os

from dashlane import alfred, cache, config

HINT = "↩ copy · ⌘↩ paste"


def field(entry, key, title, subtitle, icon, match, open_url=False):
    item = {
        "uid": f"field-{key}",
        "title": title,
        "subtitle": subtitle,
        "arg": entry["id"],
        "match": match,
        "icon": {"path": config.icon(icon)},
        "variables": {"action": f"copy:{key}", "item_id": entry["id"]},
        "mods": {
            "cmd": {
                "subtitle": f"Paste into the frontmost app · {subtitle.split(' · ')[0]}",
                "arg": entry["id"],
                "variables": {"action": f"paste:{key}", "item_id": entry["id"]},
            },
        },
    }
    if open_url:
        item["mods"]["alt"] = {
            "subtitle": f"Open {entry['url']}",
            "arg": entry["id"],
            "variables": {"action": "open-url", "item_id": entry["id"]},
        }
        item["quicklookurl"] = entry["url"]
    return item


def command(entry, key, title, subtitle, icon, action, match):
    variables = {"action": action, "item_id": entry["id"]}
    return {
        "uid": f"field-{key}",
        "title": title,
        "subtitle": subtitle,
        "arg": entry["id"],
        "match": match,
        "icon": {"path": config.icon(icon)},
        "variables": variables,
        "mods": {"cmd": {"subtitle": subtitle, "arg": entry["id"], "variables": variables}},
    }


def build(entry):
    name = entry["title"]
    items = []
    if entry["login"]:
        items.append(field(entry, "login", entry["login"], f"Login · {HINT}", "field-login", f"login email {entry['login']}"))
    items.append(field(entry, "password", "Password", f"{name} · {HINT}", "credential", "password"))
    if entry["otp"]:
        items.append(field(entry, "otp", "2FA code", f"{name} · {HINT}", "credential-otp", "2fa otp code totp"))
    if entry["url"]:
        items.append(
            field(entry, "url", entry["url"], f"Website · {HINT} · ⌥↩ open", "field-url", f"website url {entry['url']}", open_url=True)
        )
    if entry.get("secondary_login"):
        login = entry["secondary_login"]
        items.append(field(entry, "username", login, f"Username · {HINT}", "field-login", f"username {login}"))
    if entry.get("has_note"):
        items.append(field(entry, "note", "Note", f"{name} · {HINT}", "note", "note"))
    items.append(
        command(entry, "type", "Type login ⇥ password", "Type them into the frontmost app", "field-type", "type", "type autofill fill")
    )
    items.append(
        command(entry, "card", "Show item card", "Login, password, live 2FA code and website", "field-card", "card", "card show details")
    )
    return items


def main():
    entry = cache.find_credential(os.environ.get("item_id", ""))
    if not entry:
        return alfred.output([alfred.info_item("Item not found", "Sync your vault and try again", icon="warning")])
    alfred.output(build(entry))


if __name__ == "__main__":
    main()
