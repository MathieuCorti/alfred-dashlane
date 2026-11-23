# Dashlane for Alfred

Search your Dashlane vault from [Alfred](https://www.alfredapp.com), powered by the official [Dashlane CLI](https://cli.dashlane.com). Built for Alfred 6 and its new Alfred UI toolkit.

## Requirements

* Alfred 6 with the Powerpack.
* The Dashlane CLI: `brew install dashlane/tap/dashlane-cli`, then run `dcli sync` once in Terminal to log in.
* Python 3 (`/usr/bin/python3`, installed with the Xcode Command Line Tools).

## Passwords: `dash`

* ↩ Copy the password
* ⌘↩ Copy the login
* ⌥↩ Show the item card
* ⌃↩ Copy the 2FA code
* ⇧↩ Type login ⇥ password into the frontmost app
* fn↩ Open the website
* ⌘C Copy the login · ⌘L Large Type · ⇧ or ⌘Y Quick Look the website

With no query, favourites come first, then recently used items. Type `sync` or `lock` after the keyword to sync or lock the vault.

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

## External triggers

Open a card from AppleScript or another workflow with an item id:

```applescript
tell application id "com.runningwithcrayons.Alfred" to run trigger "card" in workflow "com.mathieucorti.alfred.dashlane" with argument "ITEM-ID"
```

The `note` trigger does the same for a secure note.

## Security

* Passwords, 2FA codes and notes are read from the Dashlane CLI only when you use them. The workflow caches titles, logins and websites only, in a file only your user can read.
* Copied secrets are marked as concealed so clipboard managers, Alfred's Clipboard History included, don't record them. They are cleared from the clipboard after the configured delay, unless you copied something else meanwhile.
* Logging in and unlocking happen in Terminal: your master password never goes through Alfred.

## Development

The workflow sources live in `workflow/`. `build_workflow.py` generates `info.plist` and packages the workflow:

```sh
python3 build_workflow.py            # build/Dashlane and dist/Dashlane.alfredworkflow
python3 build_workflow.py --install  # also copy the build into Alfred's workflows folder
swift tools/make_icons.swift workflow  # re-render the icons from SF Symbols
```

* `search.py` and `notes.py` are the Script Filters. They read a metadata cache that `refresh.py` rebuilds in the background.
* `action.py` runs the chosen action and tells the workflow to post a notification or open Terminal.
* `item.alfredui` and `note.alfredui` are the Alfred UI cards. Their scripts build the card when it opens; `scripts/otp` is the pulse that keeps the 2FA code up to date.
* `pasteboard.js` and `autotype.js` handle the clipboard and typing. Secrets reach them through stdin, never through command-line arguments.

## License

MIT
