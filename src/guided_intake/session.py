"""Session state: which answers are in, which question comes next, which rules fail."""
from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .parsing import parse_bool, parse_choice, parse_number
from .spec import Field, Issue, Spec


@dataclass(frozen=True)
class SetResult:
    ok: bool
    field: str
    value: Any = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "field": self.field}
        if self.ok:
            out["value"] = self.value
        else:
            out["error"] = self.message
        return out


class Session:
    def __init__(self, spec: Spec, session_id: str | None = None) -> None:
        self.spec = spec
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self._raw: dict[str, Any] = {}

    def set_value(self, name: str, raw: Any) -> SetResult:
        f = self.spec.field_named(name)
        if f is None:
            known = ", ".join(x.name for x in self.spec.fields)
            return SetResult(False, name, message=f"unknown field '{name}'. Known fields: {known}")
        try:
            value = self._coerce(f, raw)
        except ValueError as err:
            return SetResult(False, name, message=str(err))
        self._raw[name] = value
        return SetResult(True, name, value)

    def clear(self, name: str) -> bool:
        """Forget an answer so the field is asked again. Returns False if it had no stored answer."""
        return self._raw.pop(name, None) is not None

    def set_many(self, answers: dict[str, Any]) -> list[SetResult]:
        return [self.set_value(k, v) for k, v in answers.items()]

    def answers(self) -> dict[str, Any]:
        """Answers plus defaults, limited to fields that are currently relevant."""
        acc: dict[str, Any] = {}
        for f in self.spec.fields:
            if not f.is_active(acc):
                continue
            if f.name in self._raw:
                acc[f.name] = self._raw[f.name]
            elif f.default is not None:
                acc[f.name] = f.default
        return acc

    def next_field(self) -> Field | None:
        acc: dict[str, Any] = {}
        for f in self.spec.fields:
            if not f.is_active(acc):
                continue
            if f.name in self._raw:
                acc[f.name] = self._raw[f.name]
            elif f.default is not None:
                acc[f.name] = f.default
            elif f.required:
                return f
        return None

    def is_complete(self) -> bool:
        return self.next_field() is None

    def issues(self) -> list[Issue]:
        have = self.answers()
        found: list[Issue] = []
        for rule in self.spec.checks:
            if all(n in have for n in rule.needs):
                found.extend(rule.run(have))
        return found

    def can_finish(self) -> bool:
        return self.is_complete() and not any(i.severity == "error" for i in self.issues())

    def progress(self) -> dict[str, Any]:
        nxt = self.next_field()
        issues = [i.to_dict() for i in self.issues()]
        blocked = any(i["severity"] == "error" for i in issues)
        if nxt is not None:
            next_step = "Ask next_question."
        elif blocked:
            next_step = "Read the issues aloud and fix the errors, then check again."
        else:
            next_step = "All questions are answered. Call finish now. Nothing is ready until finish succeeds."
        return {
            "session_id": self.session_id,
            "spec": self.spec.name,
            "complete": nxt is None,
            "next_question": nxt.describe() if nxt else None,
            "next_step": next_step,
            "collected": self.answers(),
            "issues": issues,
        }

    @staticmethod
    def _coerce(f: Field, raw: Any) -> Any:
        if f.kind == "number":
            number = parse_number(raw, f.unit)
            if f.minimum is not None and number < f.minimum:
                raise ValueError(f"{f.name} must be at least {f.minimum:g}{_unit(f)}")
            if f.maximum is not None and number > f.maximum:
                raise ValueError(f"{f.name} must be at most {f.maximum:g}{_unit(f)}")
            return number
        if f.kind == "choice":
            return parse_choice(raw, f.choices)
        if f.kind == "bool":
            return parse_bool(raw)
        text = str(raw).strip()
        if not text:
            raise ValueError(f"{f.name} cannot be empty")
        return text


def _unit(f: Field) -> str:
    return f" {f.unit}" if f.unit else ""


class SessionStore:
    """In-memory sessions. Oldest ones are dropped once the cap is reached.

    Creating and looking up sessions is thread-safe. A single Session is not: one
    conversation is expected to be driven by one caller at a time.
    """

    def __init__(self, specs: Iterable[Spec], max_sessions: int = 500) -> None:
        self._specs = {s.name: s for s in specs}
        self._live: OrderedDict[str, Session] = OrderedDict()
        self._cap = max_sessions
        self._lock = threading.Lock()

    def spec_list(self) -> list[Spec]:
        return list(self._specs.values())

    def create(self, spec_name: str) -> Session:
        spec = self._specs.get(spec_name)
        if spec is None:
            raise KeyError(f"unknown spec '{spec_name}'. Available: {', '.join(self._specs)}")
        session = Session(spec)
        with self._lock:
            self._live[session.session_id] = session
            while len(self._live) > self._cap:
                self._live.popitem(last=False)
        return session

    def get(self, session_id: str) -> Session:
        with self._lock:
            found = self._live.get(session_id)
        if found is None:
            raise KeyError(f"no session '{session_id}'. Start one with start_intake")
        return found
