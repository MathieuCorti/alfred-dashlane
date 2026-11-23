"""Script Filter output helpers and the result items shared by both searches."""

import json
import sys

from . import cache, config, dcli


def output(items, rerun=None, variables=None):
    payload = {"items": items}
    if rerun:
        payload["rerun"] = rerun
    if variables:
        payload["variables"] = variables
    sys.stdout.write(json.dumps(payload))


def info_item(title, subtitle, icon="warning", **extra):
    item = {"title": title, "subtitle": subtitle, "valid": False, "icon": {"path": config.icon(icon)}}
    item.update(extra)
    return item


def action_item(title, subtitle, action, arg="", icon="sync", **extra):
    item = {
        "title": title,
        "subtitle": subtitle,
        "arg": arg or action,
        "variables": {"action": action},
        "icon": {"path": config.icon(icon)},
    }
    item.update(extra)
    return item


ERROR_TITLES = {
    dcli.LOGGED_OUT: "Log in to Dashlane",
    dcli.LOCKED: "Unlock your Dashlane vault",
    dcli.AUTH: "Dashlane session expired: log in again",
}


def error_items(state):
    """Items explaining why the vault can't be read, with a way to fix it."""
    kind = state.get("error")
    message = state.get("message", "")
    if kind == dcli.MISSING:
        return [
            action_item(
                "Install the Dashlane CLI",
                "dcli was not found. ↩ to open the install guide (brew install dashlane/tap/dashlane-cli)",
                "open-url",
                arg="https://cli.dashlane.com/install",
                icon="warning",
            )
        ]
    if kind in dcli.NEEDS_LOGIN:
        return [
            action_item(
                ERROR_TITLES[kind],
                f"{message} ↩ to open Terminal and run: {dcli.terminal_command(kind)}",
                "login",
                arg=kind,
                icon="login",
            )
        ]
    return [
        action_item(
            "Could not read your Dashlane vault",
            f"{message} ↩ to sync and retry",
            "sync",
            icon="warning",
        )
    ]


UTILITIES = (
    ("Sync vault", "Sync with Dashlane and reload the item list", "sync", "sync"),
    ("Lock vault", "Lock the Dashlane CLI; unlocking asks for your master password", "lock", "lock"),
)


def utility_items(query):
    words = query.lower().split()
    if not words:
        return []
    return [
        action_item(title, subtitle, action, icon=icon)
        for title, subtitle, action, icon in UTILITIES
        if all(word in title.lower() for word in words)
    ]


def rank(entries, query, fields):
    """Keep entries whose fields contain every query word, best matches first."""
    words = query.lower().split()
    if not words:
        return sorted(entries, key=lambda e: (not e.get("favorite"), -e.get("last_use", 0), e["title"].lower()))
    phrase = " ".join(words)
    ranked = []
    for entry in entries:
        haystacks = [str(entry.get(field) or "").lower() for field in fields]
        if not all(any(word in h for h in haystacks) for word in words):
            continue
        title = haystacks[0]
        if title == phrase:
            score = 0
        elif title.startswith(phrase):
            score = 1
        elif any(h.startswith(phrase) for h in haystacks[1:]):
            score = 2
        elif all(any(part.startswith(word) for part in title.replace(".", " ").split()) for word in words):
            score = 3
        else:
            score = 4
        ranked.append((score, not entry.get("favorite"), -entry.get("last_use", 0), entry["title"].lower(), entry))
    ranked.sort(key=lambda r: r[:4])
    return [r[-1] for r in ranked]


def load_or_refresh(name, query, build):
    """Shared Script Filter flow: serve the cache, refresh it in the background."""
    entries = cache.load(name)
    state = cache.load(cache.STATE) or {}
    if cache.should_refresh(name):
        cache.spawn_refresh()
    refreshing = cache.refresh_running()

    if entries is None:
        if refreshing:
            return output(
                [info_item("Loading your Dashlane vault…", "Reading items from the Dashlane CLI", icon="sync")],
                rerun=0.3,
            )
        if state.get("error"):
            return output(error_items(state))
        cache.spawn_refresh()
        return output([info_item("Loading your Dashlane vault…", "Reading items from the Dashlane CLI", icon="sync")], rerun=0.3)

    items = []
    if state.get("error"):
        items += error_items(state)
    matches = build(entries, query)
    items += matches
    utilities = utility_items(query)
    items += utilities
    if not matches and not utilities and query.strip():
        items.append(info_item(f"No match for “{query.strip()}”", "Try another word, or “sync” to reload your vault", icon="search"))
    # Rerun while a background refresh is running so new items appear on their own.
    output(items, rerun=1 if refreshing else None)
