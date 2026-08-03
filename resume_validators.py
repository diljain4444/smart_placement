"""
validators.py
------------------------------------------------------------
Lightweight, dependency-cheap validators used by app.py to give
INSTANT inline feedback in the Streamlit form, before anything is
sent to backend.py (i.e. before an LLM call is even made).

Design principle:
    - "Required" checks are enforced only at submit time (so we don't
      nag the user with "This field is required" while they're still
      typing their first character).
    - "Format" checks (email shape, phone digit count, URL shape,
      4-digit year) run live, as soon as the field is non-empty, so
      typos are caught immediately.

Every validator returns a (is_valid: bool, message: str) tuple.
`message` is empty when is_valid is True.
------------------------------------------------------------
"""

import re
from typing import Tuple

from email_validator import validate_email, EmailNotValidError

URL_RE = re.compile(r"^(https?://)?([\w-]+\.)+[a-zA-Z]{2,}([/?#].*)?$")


# ---------------------------------------------------------------
# Generic building blocks
# ---------------------------------------------------------------
def required(value: str, field_name: str) -> Tuple[bool, str]:
    """Fails only if the field is empty/whitespace-only."""
    if value is None or not str(value).strip():
        return False, f"{field_name} is required."
    return True, ""


def min_length(value: str, n: int, field_name: str) -> Tuple[bool, str]:
    if value and len(value.strip()) < n:
        return False, f"{field_name} must be at least {n} characters."
    return True, ""


# ---------------------------------------------------------------
# Field-specific validators
# ---------------------------------------------------------------
def validate_name(value: str) -> Tuple[bool, str]:
    ok, msg = required(value, "Name")
    if not ok:
        return ok, msg
    return min_length(value, 2, "Name")


def validate_email_format(value: str, required_field: bool = True) -> Tuple[bool, str]:
    """
    Live format check. If required_field is False, an empty value is
    treated as valid (caller should still run `required()` at submit
    time for required emails).
    """
    if not value or not value.strip():
        return (False, "Email is required.") if required_field else (True, "")
    try:
        validate_email(value.strip(), check_deliverability=False)
        return True, ""
    except EmailNotValidError as e:
        return False, str(e)


def validate_phone(value: str, required_field: bool = True) -> Tuple[bool, str]:
    if not value or not value.strip():
        return (False, "Phone is required.") if required_field else (True, "")
    digits = re.sub(r"\D", "", value)
    if len(digits) < 10:
        return False, "Phone number must contain at least 10 digits."
    if len(digits) > 15:
        return False, "Phone number has too many digits."
    return True, ""


def validate_url(value: str, field_name: str = "URL") -> Tuple[bool, str]:
    """URLs are optional everywhere they're used, so empty is valid."""
    if not value or not value.strip():
        return True, ""
    if not URL_RE.match(value.strip()):
        return False, f"{field_name} doesn't look like a valid URL (e.g. example.com/you)."
    return True, ""


def validate_year(value: str, field_name: str = "Year") -> Tuple[bool, str]:
    if not value or not value.strip():
        return False, f"{field_name} is required."
    v = value.strip()
    if not re.match(r"^\d{4}$", v) and v.lower() != "present":
        return False, f"{field_name} must be a 4-digit year (e.g. 2023) or 'Present'."
    return True, ""


def validate_comma_list(value: str, field_name: str) -> Tuple[bool, str]:
    """Used for Skills / Tech Stack — must yield at least one non-empty item."""
    ok, msg = required(value, field_name)
    if not ok:
        return ok, msg
    items = [i.strip() for i in value.split(",") if i.strip()]
    if not items:
        return False, f"{field_name} must contain at least one item."
    return True, ""