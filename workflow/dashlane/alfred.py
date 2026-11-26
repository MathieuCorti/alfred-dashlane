"""Script Filter output helpers and the result items shared by both searches."""

import json
import sys

from . import cache, config, dcli, favicons, usage


def output(items, rerun=None, variables=None):
    # The workflow orders results itself (usage.py); Alfred's own learning
    # would reshuffle them on top of that.
    payload = {"items": items, "skipknowledge": True}
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
    """Keep entries whose fields contain every query word, best matches first.

    Matches are grouped by how well they match; within a group, favourites come
    first, then the items you use most and most recently (see usage.py).
    """
    score = usage.scorer()
    words = query.lower().split()
    if not words:
        return sorted(entries, key=lambda e: (not e.get("favorite"), -score(e), e["title"].lower()))
    phrase = " ".join(words)
    ranked = []
    for entry in entries:
        haystacks = [str(entry.get(field) or "").lower() for field in fields]
        if not all(any(word in h for h in haystacks) for word in words):
            continue
        title = haystacks[0]
        if title.startswith(phrase):
            group = 0
        elif any(h.startswith(phrase) for h in haystacks[1:]) or all(
            any(part.startswith(word) for part in title.replace(".", " ").split()) for word in words
        ):
            group = 1
        else:
            group = 2
        ranked.append((group, not entry.get("favorite"), -score(entry), entry["title"].lower(), entry))
    ranked.sort(key=lambda r: r[:4])
    return [r[-1] for r in ranked]


LOADING = ("Loading your Dashlane vault…", "Reading items from the Dashlane CLI")


def prepare(name):
    """Load a cached list and start a background refresh when needed.

    Returns (entries, state, refreshing); entries is None when there is no cache.
    """
    entries = cache.load(name)
    state = cache.load(cache.STATE) or {}
    if cache.should_refresh(name):
        cache.spawn_refresh()
    elif entries is not None:
        favicons.maybe_spawn_fetch()
    return entries, state, cache.refresh_running()


def output_unavailable(state, refreshing):
    """Script Filter output when there is no cached list yet."""
    if state.get("error") and not refreshing:
        return output(error_items(state))
    return output([info_item(*LOADING, icon="sync")], rerun=0.3)


def load_or_refresh(name, query, build):
    """Shared Script Filter flow: serve the cache, refresh it in the background."""
    entries, state, refreshing = prepare(name)
    if entries is None:
        return output_unavailable(state, refreshing)

    errors = error_items(state) if state.get("error") else []
    # A login problem breaks every action, so it goes first. A transient error
    # goes last, so ↩ still picks the best match.
    blocking = state.get("error") in dcli.NEEDS_LOGIN or state.get("error") == dcli.MISSING
    matches = build(entries, query)
    utilities = utility_items(query)
    items = (errors if blocking else []) + matches + utilities + ([] if blocking else errors)
    if not matches and not utilities and query.strip():
        items.append(info_item(f"No match for “{query.strip()}”", "Try another word, or “sync” to reload your vault", icon="search"))
    # Rerun while a background refresh is running so new items appear on their own.
    output(items, rerun=1 if refreshing else None)
