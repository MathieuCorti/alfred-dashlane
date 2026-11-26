"""Which items you use from Alfred, so the most used and recent ones come first.

Only item ids and timestamps are stored, in the workflow cache folder.
Scores follow a frecency model: every use counts, recent uses count more.
Dashlane's own last use (browser extension, apps) counts as one extra use at
half weight, so items you have never opened from Alfred are still ordered.
"""

import time

from . import cache

USAGE = "usage.json"
KEEP_USES = 10  # most recent uses kept per item
MERGE_WITHIN = 60  # seconds: opening the field list, then copying, is one use
FORGET_AFTER = 365 * 86400

# (max age in days, weight), like Firefox's frecency buckets.
BUCKETS = ((1, 100), (4, 80), (14, 60), (31, 40), (90, 20))
OLD_WEIGHT = 10


def load():
    data = cache.load(USAGE)
    return data if isinstance(data, dict) else {}


def record(item_id, now=None):
    """Remember that the item was used. Never fails the action that called it."""
    if not item_id:
        return
    now = int(now or time.time())
    try:
        data = load()
        uses = [t for t in data.get(item_id, []) if isinstance(t, int)]
        if uses and now - uses[-1] < MERGE_WITHIN:
            uses[-1] = now
        else:
            uses.append(now)
        data[item_id] = uses[-KEEP_USES:]
        data = {key: value for key, value in data.items() if value and now - value[-1] < FORGET_AFTER}
        cache.save(USAGE, data)
    except (OSError, TypeError, ValueError):
        pass


def weight(timestamp, now):
    if not timestamp:
        return 0
    days = (now - timestamp) / 86400
    for max_days, value in BUCKETS:
        if days < max_days:
            return value
    return OLD_WEIGHT


def scorer(now=None):
    """Return a function giving an entry's frecency score."""
    now = now or time.time()
    data = load()

    def score(entry):
        local = sum(weight(t, now) for t in data.get(entry["id"], []))
        return local + weight(entry.get("last_use", 0), now) / 2

    return score
