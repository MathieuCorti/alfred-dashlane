"""Builders for Alfred UI components and JSON actions used by the item cards."""

import json
import sys

from . import dcli

SECONDARY = "secondaryLabelColor"
MASK = "••••••••••••"


def emit(actions):
    sys.stdout.write(json.dumps(actions))


def label(text, id=None, colour=None, font=None, selectable=False, **extra):
    component = {"type": "label", "text": text, "selectable": selectable}
    if id:
        component["id"] = id
    if colour:
        component["colour"] = colour
    if font:
        component["font"] = font
    component.update(extra)
    return component


def script_action(script, *args, async_=True):
    return {"type": "script", "src": f"scripts/{script}", "args": list(args), "async": async_}


def finish_action(action):
    """Close the UI and hand the item to the workflow's action script."""
    return {
        "type": "json",
        "src": {"finish": {"args": "{var:item_id}", "variables": {"action": action}}},
    }


def icon_button(symbol, tooltip, action, shortcut=None, id=None, enabled=True):
    button = {
        "type": "button",
        "bordered": False,
        "image": {"type": "symbol", "src": symbol, "size": {"width": 15}},
        "tooltip": tooltip,
        "enabled": enabled,
        "accessibility": {"label": tooltip.split(" (")[0]},
        "events": [{"triggers": "actioned", "action": action}],
    }
    if shortcut:
        button["shortcut"] = shortcut
    if id:
        button["id"] = id
    return button


def text_button(text, action, shortcut=None, enabled=True):
    button = {
        "type": "button",
        "text": text,
        "enabled": enabled,
        "events": [{"triggers": "actioned", "action": action}],
    }
    if shortcut:
        button["shortcut"] = shortcut
    return button


def inline(components, direction="horizontal", spacing=4, **extra):
    view = {"type": "view", "layout": "inline", "direction": direction, "spacing": spacing, "components": components}
    view.update(extra)
    return view


def field_row(name, value, buttons, stretch=True):
    """Two components for a form layout: the field name and value + buttons."""
    value_constraints = {"region": "centre", "position": "left"}
    if stretch:
        value_constraints["stretch"] = "horizontal"
    return [
        label(name, colour=SECONDARY, constraints={"position": "right"}),
        {
            "type": "view",
            "layout": "border",
            "spacing": 8,
            "components": [
                {**value, "constraints": value_constraints},
                {**inline(buttons, spacing=2), "constraints": {"region": "right"}},
            ],
        },
    ]


def header(symbol, tint, title, subtitle):
    return {
        "type": "view",
        "layout": "border",
        "spacing": 12,
        "components": [
            {
                "type": "imageview",
                "contenttintcolour": tint,
                "image": {"type": "symbol", "src": symbol, "size": {"width": 30}},
                "constraints": {"region": "left", "position": "centre"},
            },
            {
                **inline(
                    [
                        label(title, font={"size": "large", "weight": "semibold"}),
                        label(subtitle or " ", colour=SECONDARY),
                    ],
                    direction="vertical",
                    spacing=2,
                ),
                "constraints": {"region": "centre"},
            },
        ],
    }


def separator():
    return {"type": "view", "layout": "stack", "background": "separatorColor", "constraints": {"size": {"height": 1}}}


def status(text, error=False):
    return {"update": {"ids": {"status": {"text": text, "colour": "systemRedColor" if error else SECONDARY}}}}


def error_text(error):
    if isinstance(error, dcli.DcliError) and error.kind in dcli.NEEDS_LOGIN:
        return f"{error.message} Run your Dashlane keyword in Alfred to log in."
    return str(error)
