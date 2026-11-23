#!/usr/bin/env python3
"""Build the Dashlane Alfred workflow.

    python3 build_workflow.py            # build/ and dist/Dashlane.alfredworkflow
    python3 build_workflow.py --install  # also copy the build into Alfred's workflows folder
"""

import argparse
import json
import plistlib
import shutil
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "workflow"
BUILD_DIR = ROOT / "build" / "Dashlane"
DIST_DIR = ROOT / "dist"

VERSION = "1.0.0"
BUNDLE_ID = "com.mathieucorti.alfred.dashlane"
INSTALL_FOLDER = "user.workflow.dashlane-mathieucorti"

# Object uids (stable so Alfred keeps knowledge and positions across builds).
SF_SEARCH = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C01"
SF_NOTES = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C02"
ROUTE = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C03"
UI_ITEM = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C04"
UI_NOTE = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C05"
ACTION = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C06"
NEXT = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C07"
NOTIFY = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C08"
TERMINAL = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C09"
ROUTE_CARD = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C10"
ROUTE_NOTE_CARD = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C11"
NEXT_NOTIFY = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C12"
NEXT_TERMINAL = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C13"
TRIGGER_CARD = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C14"
TRIGGER_NOTE = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C15"
SF_FIELDS = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C16"
ROUTE_FIELDS = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C17"
CLEAR_ARG = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C18"
TRIGGER_FIELDS = "4C1E0B6A-2A5E-4E43-9C0B-1D5E0A7B5C19"

MODIFIERS = {"none": 0, "cmd": 1 << 20, "alt": 1 << 19, "ctrl": 1 << 18, "shift": 1 << 17, "fn": 1 << 23}

FILES = [
    "search.py",
    "notes.py",
    "fields.py",
    "action.py",
    "refresh.py",
    "pasteboard.js",
    "autotype.js",
    "icon.png",
    "dashlane",
    "icons",
    "item.alfredui",
    "note.alfredui",
]
EXECUTABLES = ["item.alfredui/scripts/card", "item.alfredui/scripts/otp", "note.alfredui/scripts/note"]


def workflow_readme():
    """The README shown in Alfred: the repository README without the Development part."""
    text = (ROOT / "README.md").read_text()
    return text.split("\n## Development")[0].strip() + "\n"


def connection(destination, modifiers=0, source_output=None):
    conn = {"destinationuid": destination, "modifiers": modifiers, "modifiersubtext": "", "vitoclose": False}
    if source_output:
        conn["sourceoutputuid"] = source_output
    return conn


def script_filter(uid, keyword_var, script, title, subtext):
    return {
        "uid": uid,
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            "alfredfiltersresults": False,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": False,
            "argumenttrimmode": 0,
            "argumenttype": 1,
            "escaping": 102,
            "keyword": "{var:%s}" % keyword_var,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 1,
            "runningsubtext": "Searching your vault…",
            "script": f'/usr/bin/python3 {script} "$1"',
            "scriptargtype": 1,
            "scriptfile": "",
            "subtext": subtext,
            "title": title,
            "type": 0,
            "withspace": True,
        },
    }


def fields_filter(uid):
    """Keyword-less Script Filter listing one credential's fields (reached from ROUTE)."""
    return {
        "uid": uid,
        "type": "alfred.workflow.input.scriptfilter",
        "version": 3,
        "config": {
            "alfredfiltersresults": True,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": True,
            "argumenttrimmode": 0,
            "argumenttype": 1,
            "escaping": 102,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 1,
            "runningsubtext": "Loading item…",
            "script": '/usr/bin/python3 fields.py "$1"',
            "scriptargtype": 1,
            "scriptfile": "",
            "skipuniversalaction": True,
            "subtext": "Copy or paste a field of the item",
            "title": "Dashlane item",
            "type": 0,
            "withspace": False,
        },
    }


def conditional(uid, variable, branches):
    return {
        "uid": uid,
        "type": "alfred.workflow.utility.conditional",
        "version": 1,
        "config": {
            "conditions": [
                {
                    "inputstring": "{var:%s}" % variable,
                    "matchcasesensitive": False,
                    "matchmode": 0,
                    "matchstring": match,
                    "outputlabel": label,
                    "uid": branch_uid,
                }
                for branch_uid, match, label in branches
            ],
            "elselabel": "else",
            "hideelse": False,
        },
    }


def external_trigger(uid, trigger_id):
    return {
        "uid": uid,
        "type": "alfred.workflow.trigger.external",
        "version": 1,
        "config": {"availableviaurlhandler": False, "triggerid": trigger_id},
    }


def alfred_ui(uid, path):
    return {
        "uid": uid,
        "type": "alfred.workflow.userinterface.alfredui",
        "version": 1,
        "config": {"launchmode": 0, "path": path, "stackview": True},
    }


def user_configuration():
    return [
        {
            "type": "textfield",
            "variable": "keyword",
            "label": "Passwords keyword",
            "description": "",
            "config": {"default": "dash", "placeholder": "", "required": True, "trim": True},
        },
        {
            "type": "textfield",
            "variable": "notes_keyword",
            "label": "Secure notes keyword",
            "description": "",
            "config": {"default": "dashnote", "placeholder": "", "required": True, "trim": True},
        },
        {
            "type": "popupbutton",
            "variable": "clear_clipboard_after",
            "label": "Clear copied secrets",
            "description": "Passwords, 2FA codes and notes are removed from the clipboard after this delay, unless you copied something else meanwhile.",
            "config": {
                "default": "30",
                "pairs": [
                    ["After 15 seconds", "15"],
                    ["After 30 seconds", "30"],
                    ["After 1 minute", "60"],
                    ["After 2 minutes", "120"],
                    ["Never", "0"],
                ],
            },
        },
        {
            "type": "popupbutton",
            "variable": "cache_max_age",
            "label": "Refresh item list",
            "description": "How often the list of items (titles, logins and websites only) is reloaded from the Dashlane CLI in the background.",
            "config": {
                "default": "60",
                "pairs": [
                    ["Every 15 minutes", "15"],
                    ["Every 30 minutes", "30"],
                    ["Every hour", "60"],
                    ["Every 4 hours", "240"],
                ],
            },
        },
        {
            "type": "checkbox",
            "variable": "autotype_submit",
            "label": "Typing",
            "description": "When typing a login and password into an app (⇧↩), press Return at the end.",
            "config": {"default": False, "required": False, "text": "Press Return after the password"},
        },
        {
            "type": "textfield",
            "variable": "dcli_path",
            "label": "Dashlane CLI path",
            "description": "Leave empty to find dcli automatically (Homebrew).",
            "config": {"default": "", "placeholder": "/opt/homebrew/bin/dcli", "required": False, "trim": True},
        },
    ]


def build_info_plist():
    route_targets = [
        (ROUTE_FIELDS, "fields", "Item fields"),
        (ROUTE_CARD, "card", "Credential card"),
        (ROUTE_NOTE_CARD, "note-card", "Note card"),
    ]
    objects = [
        script_filter(SF_SEARCH, "keyword", "search.py", "Search Dashlane", "Copy passwords, logins and 2FA codes"),
        script_filter(SF_NOTES, "notes_keyword", "notes.py", "Search Dashlane notes", "Show or copy secure notes"),
        conditional(ROUTE, "action", route_targets),
        {
            # A Script Filter reached mid-stream shows its input as the query:
            # keep the item id in a variable and start the field list empty.
            "uid": CLEAR_ARG,
            "type": "alfred.workflow.utility.argument",
            "version": 1,
            "config": {"argument": "", "passthroughargument": False, "variables": {"item_id": "{query}"}},
        },
        fields_filter(SF_FIELDS),
        external_trigger(TRIGGER_CARD, "card"),
        external_trigger(TRIGGER_NOTE, "note"),
        external_trigger(TRIGGER_FIELDS, "fields"),
        alfred_ui(UI_ITEM, "item.alfredui"),
        alfred_ui(UI_NOTE, "note.alfredui"),
        {
            "uid": ACTION,
            "type": "alfred.workflow.action.script",
            "version": 2,
            "config": {
                "concurrently": False,
                "escaping": 102,
                "script": '/usr/bin/python3 action.py "$1"',
                "scriptargtype": 1,
                "scriptfile": "",
                "type": 0,
            },
        },
        conditional(NEXT, "next", [(NEXT_NOTIFY, "notify", "Notify"), (NEXT_TERMINAL, "terminal", "Terminal")]),
        {
            "uid": NOTIFY,
            "type": "alfred.workflow.output.notification",
            "version": 1,
            "config": {
                "lastpathcomponent": False,
                "onlyshowifquerypopulated": True,
                "removeextension": False,
                "text": "{query}",
                "title": "{var:notify_title}",
            },
        },
        {
            "uid": TERMINAL,
            "type": "alfred.workflow.action.terminalcommand",
            "version": 1,
            "config": {"escaping": 0, "script": "{query}"},
        },
    ]
    connections = {
        SF_SEARCH: [connection(ROUTE, mask) for mask in MODIFIERS.values()],
        SF_NOTES: [connection(ROUTE, MODIFIERS[key]) for key in ("none", "cmd")],
        ROUTE: [
            connection(CLEAR_ARG, source_output=ROUTE_FIELDS),
            connection(UI_ITEM, source_output=ROUTE_CARD),
            connection(UI_NOTE, source_output=ROUTE_NOTE_CARD),
            connection(ACTION),
        ],
        TRIGGER_FIELDS: [connection(CLEAR_ARG)],
        CLEAR_ARG: [connection(SF_FIELDS)],
        SF_FIELDS: [connection(ROUTE, MODIFIERS[key]) for key in ("none", "cmd", "alt")],
        TRIGGER_CARD: [connection(UI_ITEM)],
        TRIGGER_NOTE: [connection(UI_NOTE)],
        UI_ITEM: [connection(ACTION)],
        UI_NOTE: [connection(ACTION)],
        ACTION: [connection(NEXT)],
        NEXT: [
            connection(NOTIFY, source_output=NEXT_NOTIFY),
            connection(TERMINAL, source_output=NEXT_TERMINAL),
        ],
    }
    positions = {
        SF_SEARCH: (40, 60),
        SF_NOTES: (40, 260),
        ROUTE: (260, 160),
        TRIGGER_FIELDS: (260, -110),
        CLEAR_ARG: (430, -90),
        SF_FIELDS: (560, -110),
        TRIGGER_CARD: (260, 0),
        TRIGGER_NOTE: (260, 300),
        UI_ITEM: (430, 30),
        UI_NOTE: (430, 170),
        ACTION: (620, 300),
        NEXT: (800, 300),
        NOTIFY: (970, 230),
        TERMINAL: (970, 380),
    }
    return {
        "bundleid": BUNDLE_ID,
        "category": "Productivity",
        "connections": connections,
        "createdby": "Mathieu Corti",
        "description": "Search your Dashlane vault: passwords, 2FA codes and secure notes",
        "disabled": False,
        "name": "Dashlane",
        "objects": objects,
        "readme": workflow_readme(),
        "uidata": {uid: {"xpos": float(x), "ypos": float(y)} for uid, (x, y) in positions.items()},
        "userconfigurationconfig": user_configuration(),
        "variablesdontexport": [],
        "version": VERSION,
        "webaddress": "https://github.com/MathieuCorti/alfred-dashlane",
    }


def copy_sources():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    for name in FILES:
        source = SRC / name
        if source.is_dir():
            shutil.copytree(source, BUILD_DIR / name, ignore=ignore)
        else:
            shutil.copy2(source, BUILD_DIR / name)
    for name in EXECUTABLES:
        target = BUILD_DIR / name
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for ui_json in BUILD_DIR.glob("*.alfredui/ui.json"):
        json.loads(ui_json.read_text())  # Fail the build on invalid JSON.


def alfred_workflows_dir():
    prefs = Path.home() / "Library/Application Support/Alfred/prefs.json"
    current = json.loads(prefs.read_text())["current"]
    return Path(current).expanduser() / "workflows"


def install():
    target = alfred_workflows_dir() / INSTALL_FOLDER
    target.mkdir(exist_ok=True)
    # Keep prefs.plist: Alfred stores the user's configuration there.
    subprocess.run(
        ["rsync", "-a", "--delete", "--exclude", "prefs.plist", f"{BUILD_DIR}/", f"{target}/"],
        check=True,
    )
    # Make Alfred pick up the new info.plist right away.
    subprocess.run(
        ["osascript", "-e", f'tell application id "com.runningwithcrayons.Alfred" to reload workflow "{BUNDLE_ID}"'],
        check=False,
        capture_output=True,
    )
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true", help="copy the build into Alfred")
    args = parser.parse_args()

    copy_sources()
    with (BUILD_DIR / "info.plist").open("wb") as handle:
        plistlib.dump(build_info_plist(), handle, sort_keys=False)

    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / "Dashlane.alfredworkflow"
    if target.exists():
        target.unlink()
    archive = shutil.make_archive(str(DIST_DIR / "Dashlane"), "zip", root_dir=BUILD_DIR)
    Path(archive).rename(target)
    print(target)

    if args.install:
        print(f"Installed in {install()}")


if __name__ == "__main__":
    main()
