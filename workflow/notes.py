"""Script Filter: search Dashlane secure notes."""

import sys

from dashlane import alfred, cache, config

MAX_RESULTS = 60


def note_item(entry):
    return {
        "uid": f"note-{entry['id']}",
        "title": entry["title"],
        "subtitle": ("Secured · " if entry.get("secured") else "") + "↩ show note · ⌘↩ copy its content",
        "arg": entry["id"],
        "autocomplete": entry["title"],
        "icon": {"path": config.icon("note")},
        "variables": {"action": "note-card"},
        "mods": {
            "cmd": {
                "subtitle": "Copy the note content",
                "arg": entry["id"],
                "variables": {"action": "copy-note"},
            },
        },
    }


def build(entries, query):
    matches = alfred.rank(entries, query, ("title",))
    return [note_item(entry) for entry in matches[:MAX_RESULTS]]


if __name__ == "__main__":
    alfred.load_or_refresh(cache.NOTES, sys.argv[1] if len(sys.argv) > 1 else "", build)
