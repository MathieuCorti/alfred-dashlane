"""Background job: download the website icons that are not cached yet."""

from dashlane import favicons

if __name__ == "__main__":
    favicons.fetch_missing()
