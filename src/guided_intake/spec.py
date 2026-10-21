"""Declarative description of what an intake has to collect."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

Kind = Literal["number", "choice", "text", "bool"]
Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Field:
    name: str
    question: str
    kind: Kind = "number"
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()
    default: Any = None
    required: bool = True
    # Receives the answers collected so far. Lets a field appear only when relevant.
    active_when: Callable[[dict[str, Any]], bool] | None = None
    # Extra context for the assistant, kept apart from the question that is spoken aloud.
    hint: str | None = None

    def is_active(self, answers: dict[str, Any]) -> bool:
        return self.active_when is None or bool(self.active_when(answers))

    def describe(self) -> dict[str, Any]:
        info: dict[str, Any] = {"name": self.name, "question": self.question, "kind": self.kind}
        if self.unit:
            info["unit"] = self.unit
        if self.minimum is not None:
            info["minimum"] = self.minimum
        if self.maximum is not None:
            info["maximum"] = self.maximum
        if self.choices:
            info["choices"] = list(self.choices)
        if self.hint:
            info["hint"] = self.hint
        return info


@dataclass(frozen=True)
class Issue:
    severity: Severity
    message: str
    fields: tuple[str, ...] = ()
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "severity": self.severity,
            "message": self.message,
            "fields": list(self.fields),
        }
        if self.suggestion:
            out["suggestion"] = self.suggestion
        return out


@dataclass(frozen=True)
class Check:
    """A cross-field rule. It only runs once every field in `needs` has a value."""

    name: str
    needs: tuple[str, ...]
    run: Callable[[dict[str, Any]], list[Issue]]


@dataclass(frozen=True)
class Spec:
    name: str
    title: str
    description: str
    fields: tuple[Field, ...]
    checks: tuple[Check, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for f in self.fields:
            if f.name in seen:
                raise ValueError(f"duplicate field name in spec '{self.name}': {f.name}")
            seen.add(f.name)

    def field_named(self, name: str) -> Field | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None
