"""Turn loosely spoken or typed answers into clean values.

Error messages are written so an assistant can read them straight back to the user.
"""
from __future__ import annotations

import re
from typing import Any

_TO_MM = {
    "mm": 1.0, "millimeter": 1.0, "millimeters": 1.0, "millimetre": 1.0, "millimetres": 1.0,
    "cm": 10.0, "centimeter": 10.0, "centimeters": 10.0, "centimetre": 10.0, "centimetres": 10.0,
    "m": 1000.0, "meter": 1000.0, "meters": 1000.0, "metre": 1000.0, "metres": 1000.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4, '"': 25.4,
}
_NUMBER = re.compile(r"""^\s*(-?(?:\d+\.?\d*|\.\d+))\s*([a-zA-Z"]*)\s*$""")
_TRUE = {"yes", "y", "true", "yeah", "yep", "sure", "ok", "okay"}
_FALSE = {"no", "n", "false", "nope", "nah"}


def parse_number(raw: Any, unit: str | None) -> float:
    if isinstance(raw, bool):
        raise ValueError("I need a number here, not a yes or no")
    if isinstance(raw, (int, float)):
        return float(raw)
    hit = _NUMBER.match(str(raw))
    if not hit:
        raise ValueError(f"I could not read '{raw}' as a number")
    amount, suffix = float(hit.group(1)), hit.group(2).lower()
    if not suffix:
        return amount
    if unit == "mm" and suffix in _TO_MM:
        return round(amount * _TO_MM[suffix], 3)
    if unit and suffix == unit.lower():
        return amount
    expected = unit or "a plain number"
    raise ValueError(f"I expected {expected} but heard '{suffix}'")


def parse_choice(raw: Any, options: tuple[str, ...]) -> str:
    wanted = str(raw).strip().lower()
    lowered = {opt.lower(): opt for opt in options}
    if wanted in lowered:
        return lowered[wanted]
    starts = [opt for low, opt in lowered.items() if wanted and low.startswith(wanted)]
    if len(starts) == 1:
        return starts[0]
    raise ValueError(f"'{raw}' is not one of: {', '.join(options)}")


def parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    word = str(raw).strip().lower()
    if word in _TRUE:
        return True
    if word in _FALSE:
        return False
    raise ValueError(f"I could not tell if '{raw}' means yes or no")
