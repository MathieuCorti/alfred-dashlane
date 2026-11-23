# Dashlane for Alfred

Search your Dashlane vault from [Alfred](https://www.alfredapp.com): copy or paste passwords, logins and 2FA codes, and read secure notes. Built on the official [Dashlane CLI](https://cli.dashlane.com) and Alfred 6's new Alfred UI.

## Installation

1. Install the Dashlane CLI: `brew install dashlane/tap/dashlane-cli`.
2. Download `Dashlane.alfredworkflow` from the [latest release](https://github.com/MathieuCorti/alfred-dashlane/releases/latest) and open it.

Requires Alfred 6 with the Powerpack, and Python 3 (`/usr/bin/python3`, installed with the Xcode Command Line Tools).

<!-- workflow-readme -->
## Setup

Log in to the [Dashlane CLI](https://cli.dashlane.com) once in Terminal with `dcli sync`. Typing and pasting into other apps need Alfred to have Accessibility access in System Settings → Privacy & Security → Accessibility.

## Usage

Search your Dashlane logins via the `dash` keyword.

* <kbd>↩</kbd> Show the item’s fields.
* <kbd>⌘</kbd><kbd>↩</kbd> Copy the password.
* <kbd>⌥</kbd><kbd>↩</kbd> Show the item card.
* <kbd>⌃</kbd><kbd>↩</kbd> Copy the 2FA code.
* <kbd>⇧</kbd><kbd>↩</kbd> Type login and password into the frontmost app.
* <kbd>fn</kbd><kbd>↩</kbd> Open the website.
* <kbd>⌘</kbd><kbd>Y</kbd> Quick Look the website.

With no query, favourites come first, then recently used items. Search for `sync` or `lock` with the same keyword to sync or lock the vault.

Copy or paste a single field of an item from its field list: login, password, 2FA code, website, username and note.

* <kbd>↩</kbd> Copy the field.
* <kbd>⌘</kbd><kbd>↩</kbd> Paste the field into the frontmost app, then restore the clipboard.
* <kbd>⌥</kbd><kbd>↩</kbd> Open the website.

The item card shows the login, website and a live 2FA code with its countdown.

* <kbd>↩</kbd> Copy the password.
* <kbd>⌘</kbd><kbd>R</kbd> Reveal the password.
* <kbd>⌘</kbd><kbd>↩</kbd> Copy the login.
* <kbd>⌃</kbd><kbd>↩</kbd> Copy the 2FA code.
* <kbd>⇧</kbd><kbd>↩</kbd> Type login and password into the frontmost app.
* <kbd>⌘</kbd><kbd>O</kbd> Open the website.

Read secure notes via the `dashnote` keyword.

* <kbd>↩</kbd> Show the note.
* <kbd>⌘</kbd><kbd>↩</kbd> Copy the note.

Notes marked as secured in Dashlane open hidden: press <kbd>⌘</kbd><kbd>R</kbd> to show them.

Copied passwords, 2FA codes and notes are kept off clipboard managers and cleared after the delay set in the Workflow’s Configuration. Website icons are downloaded straight from each site; for sites that don’t give theirs, the Workflow’s Configuration can let DuckDuckGo fill them in.
<!-- /workflow-readme -->

## Security

* Passwords, 2FA codes and notes are read from the Dashlane CLI only when you use them. The workflow caches titles, logins and websites only, in files only your user can read.
* Copied secrets stay on this Mac (no Universal Clipboard) and are marked as concealed, so clipboard managers, Alfred's Clipboard History included, don't record them. They are cleared from the clipboard after the configured delay, unless you copied something else meanwhile.
* Pasting puts your previous clipboard back right after the paste.
* Only http and https websites are opened.
* Website icons are downloaded straight from each site, like a browser visiting it. By default no third-party icon service is used, since it would learn which sites you have accounts on. Turn icons off in the workflow configuration.
* Some sites answer but don't give their icon (bot protection such as Cloudflare, or pages built by scripts). The optional “Fill missing icons from DuckDuckGo” setting, off by default, asks DuckDuckGo's free icon service for those sites only, which then learns which of them you have accounts on. Sites that are down, unknown or internal (private IP addresses: intranet, VPN) are never sent.
* Logging in and unlocking happen in Terminal: your master password never goes through Alfred.

## External triggers

Open a card from AppleScript or another workflow with an item id:

```applescript
tell application id "com.runningwithcrayons.Alfred" to run trigger "card" in workflow "com.motystudio.dashlane" with argument "ITEM-ID"
```

The `fields` trigger opens the item's field list, and `note` opens a secure note.

## Development

The workflow sources live in `workflow/`. `build_workflow.py` generates `info.plist` and packages the workflow:

```sh
python3 build_workflow.py            # build/Dashlane and dist/Dashlane.alfredworkflow
python3 build_workflow.py --install  # also copy the build into Alfred's workflows folder
swift tools/make_icons.swift workflow  # re-render the icons
```

The text between the `workflow-readme` markers in this README becomes the readme shown in Alfred.

* `search.py`, `fields.py` and `notes.py` are the Script Filters. They read a metadata cache that `refresh.py` rebuilds in the background.
* `action.py` runs the chosen action and tells the workflow to post a notification or open Terminal.
* `item.alfredui` and `note.alfredui` are the Alfred UI cards. Their scripts build the card when it opens; `scripts/otp` is the pulse that keeps the 2FA code up to date.
* `fetch_favicons.py` downloads missing website icons in the background (`dashlane/favicons.py`).
* `pasteboard.js` and `autotype.js` handle the clipboard and typing. Secrets reach them through stdin, never through command-line arguments.

## License

MIT
