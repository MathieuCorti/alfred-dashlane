"""Background job: reload the vault metadata cache from dcli.

Started by the Script Filters. Exits right away if another refresh holds the lock.
"""

from dashlane import cache, dcli

if __name__ == "__main__":
    try:
        cache.refresh()
    except dcli.DcliError:
        pass  # Recorded in state.json; the Script Filters explain it.
