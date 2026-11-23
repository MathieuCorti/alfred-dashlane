# Dashlane for Alfred

Search your Dashlane vault from [Alfred](https://www.alfredapp.com), powered by the official [Dashlane CLI](https://cli.dashlane.com). Built for Alfred 6 and its new Alfred UI toolkit.

## Requirements

* Alfred 6 with the Powerpack.
* The Dashlane CLI: `brew install dashlane/tap/dashlane-cli`, then run `dcli sync` once in Terminal to log in.
* Python 3 (`/usr/bin/python3`, installed with the Xcode Command Line Tools).

## Passwords: `dash`

* ↩ Open the item's fields
* ⌘↩ Copy the password
* ⌥↩ Show the item card
* ⌃↩ Copy the 2FA code
* ⇧↩ Type login ⇥ password into the frontmost app
* fn↩ Open the website
* ⌘C Copy the login · ⌘L Large Type · ⇧ or ⌘Y Quick Look the website

With no query, favourites come first, then recently used items. Type `sync` or `lock` after the keyword to sync or lock the vault.

### Item fields

↩ on a result lists its login, password, 2FA code, website, username and note, plus "Type login ⇥ password" and "Show item card". Type to filter them; Alfred learns the ones you use most.

* ↩ Copy the field
* ⌘↩ Paste it into the frontmost app
* ⌥↩ Open the website (website field)

### Item card

The card is a native Alfred UI view that shows the login, website and a live 2FA code with its countdown. ⎋ goes back to the results.

* ↩ Copy the password · ⌘R Reveal it
* ⌘↩ Copy the login
* ⌃↩ Copy the 2FA code
* ⇧↩ Close and type login ⇥ password into the frontmost app
* ⌘O Open the website

## Secure notes: `dashnote`

* ↩ Show the note
* ⌘↩ Copy its content

Notes marked as secured in Dashlane open hidden in the card: press ⌘R to show them.

## External triggers

Open a card from AppleScript or another workflow with an item id:

```applescript
tell application id "com.runningwithcrayons.Alfred" to run trigger "card" in workflow "com.motystudio.dashlane" with argument "ITEM-ID"
```

The `fields` trigger opens the item's field list, and `note` opens a secure note.

## Security

* Passwords, 2FA codes and notes are read from the Dashlane CLI only when you use them. The workflow caches titles, logins and websites only, in files only your user can read.
* Copied secrets stay on this Mac (no Universal Clipboard) and are marked as concealed, so clipboard managers, Alfred's Clipboard History included, don't record them. They are cleared from the clipboard after the configured delay, unless you copied something else meanwhile.
* Pasting (⌘↩ in the item fields) puts your previous clipboard back right after the paste.
* Only http and https websites are opened.
* Logging in and unlocking happen in Terminal: your master password never goes through Alfred.

Typing and pasting need Alfred to have Accessibility access (System Settings › Privacy & Security › Accessibility).

## Development

The workflow sources live in `workflow/`. `build_workflow.py` generates `info.plist` and packages the workflow:

```sh
python3 build_workflow.py            # build/Dashlane and dist/Dashlane.alfredworkflow
python3 build_workflow.py --install  # also copy the build into Alfred's workflows folder
swift tools/make_icons.swift workflow  # re-render the icons from SF Symbols
```

* `search.py`, `fields.py` and `notes.py` are the Script Filters. They read a metadata cache that `refresh.py` rebuilds in the background.
* `action.py` runs the chosen action and tells the workflow to post a notification or open Terminal.
* `item.alfredui` and `note.alfredui` are the Alfred UI cards. Their scripts build the card when it opens; `scripts/otp` is the pulse that keeps the 2FA code up to date.
* `pasteboard.js` and `autotype.js` handle the clipboard and typing. Secrets reach them through stdin, never through command-line arguments.

## License

MIT
