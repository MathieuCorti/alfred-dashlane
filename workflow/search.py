"""Script Filter: search Dashlane credentials."""

import sys

from dashlane import alfred, cache, config

MAX_RESULTS = 60


def credential_item(entry):
    login = entry["login"]
    url = entry["url"]
    has_otp = bool(entry["otp"])
    details = [part for part in (login, entry["domain"]) if part]
    if has_otp:
        details.append("2FA")
    subtitle = " · ".join(details) or "No login or website"

    def mod(subtitle, action, valid=True):
        return {
            "subtitle": subtitle,
            "arg": entry["id"],
            "valid": valid,
            "variables": {"action": action, "item_id": entry["id"]},
        }

    item = {
        "uid": entry["id"],
        "title": entry["title"],
        "subtitle": subtitle,
        "arg": entry["id"],
        "autocomplete": entry["title"],
        "icon": {"path": config.icon("credential-otp" if has_otp else "credential")},
        "text": {"copy": login, "largetype": login or entry["title"]},
        "variables": {"action": "fields", "item_id": entry["id"]},
        "mods": {
            "cmd": mod("Copy the password", "copy:password"),
            "alt": mod("Show item card", "card"),
            "ctrl": mod("Copy 2FA code" if has_otp else "This item has no 2FA code", "copy:otp", has_otp),
            "shift": mod("Type login ⇥ password into the frontmost app", "type"),
            "fn": mod(f"Open {url}" if url else "This item has no website", "open-url", bool(url)),
        },
    }
    if url:
        item["quicklookurl"] = url
    return item


def build(entries, query):
    matches = alfred.rank(entries, query, ("title", "domain", "login", "secondary_login"))
    return [credential_item(entry) for entry in matches[:MAX_RESULTS]]


if __name__ == "__main__":
    alfred.load_or_refresh(cache.CREDENTIALS, sys.argv[1] if len(sys.argv) > 1 else "", build)
