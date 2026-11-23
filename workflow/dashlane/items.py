"""Credential fields, shared by the field list, the actions and the item card."""

from . import cache, dcli

FIELD_NAMES = {
    "login": "Login",
    "username": "Username",
    "password": "Password",
    "otp": "2FA code",
    "url": "Website",
    "note": "Note",
}


def credential(item_id):
    entry = cache.find_credential(item_id)
    if not entry:
        raise dcli.DcliError(dcli.FAILED, "This item is not in the local list. Sync your vault and try again.")
    return entry


def field_value(entry, field):
    """Return (value, is_secret, detail). value is "" when the item has no such field."""
    if field == "login":
        return entry.get("login", ""), False, ""
    if field == "username":
        return entry.get("secondary_login", ""), False, ""
    if field == "url":
        return entry.get("url", ""), False, ""
    if field == "password":
        return dcli.read(entry["id"], "password"), True, ""
    if field == "note":
        return dcli.read(entry["id"], "note"), True, ""
    if field == "otp":
        if not entry.get("otp"):
            return "", True, ""
        code, remaining = dcli.read_otp(entry["id"], entry["otp"])
        return code, True, f"valid for {remaining} s"
    raise ValueError(f"Unknown field: {field}")


def web_url(url):
    """Only open real web addresses: vault URLs may come from shared items."""
    return url if url.lower().startswith(("https://", "http://")) else ""
