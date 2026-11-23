"""Background job: reload the vault metadata cache from dcli."""

from dashlane import cache, dcli

if __name__ == "__main__":
    try:
        cache.refresh()
    except dcli.DcliError:
        pass  # Recorded in state.json; the Script Filters explain it.
    finally:
        cache.release_refresh_lock()
