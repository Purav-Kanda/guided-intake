"""Register intake tools on an MCP server so any agent can run a guided intake.

Tools never raise for bad user input. They return {"ok": False, "error": ...} so the
agent can read the problem out loud and ask again.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import MCPServer

from .session import Session, SessionStore

OnFinish = Callable[[Session], dict[str, Any]]


def register_intake_tools(server: MCPServer, store: SessionStore, on_finish: OnFinish) -> None:
    @server.tool(description="List the kinds of things this server can collect details for.")
    def list_specs() -> list[dict[str, str]]:
        return [{"name": s.name, "title": s.title, "description": s.description} for s in store.spec_list()]

    @server.tool(description="Start a new intake. Returns a session_id and the first question to ask.")
    def start_intake(spec_name: str) -> dict[str, Any]:
        try:
            return {"ok": True, **store.create(spec_name).progress()}
        except KeyError as err:
            return {"ok": False, "error": err.args[0]}

    @server.tool(
        description=(
            "Save one or more answers. Pass field names mapped to what the user said, "
            "for example {'width': '12 cm'}. Numbers with units are converted. "
            "Returns per-field results plus the next question."
        )
    )
    def submit_answers(session_id: str, answers: dict[str, str]) -> dict[str, Any]:
        try:
            session = store.get(session_id)
        except KeyError as err:
            return {"ok": False, "error": err.args[0]}
        results = [r.to_dict() for r in session.set_many(answers)]
        return {"ok": all(r["ok"] for r in results), "results": results, **session.progress()}

    @server.tool(description="Get the current question, collected answers and any rule problems.")
    def review(session_id: str) -> dict[str, Any]:
        try:
            return {"ok": True, **store.get(session_id).progress()}
        except KeyError as err:
            return {"ok": False, "error": err.args[0]}

    @server.tool(
        description=(
            "Finish the intake once every question is answered and no rule reports an error. "
            "Runs the server's final action and returns its result."
        )
    )
    def finish(session_id: str) -> dict[str, Any]:
        try:
            session = store.get(session_id)
        except KeyError as err:
            return {"ok": False, "error": err.args[0]}
        if not session.is_complete():
            return {"ok": False, "error": "questions are still open", **session.progress()}
        blocking = [i.to_dict() for i in session.issues() if i.severity == "error"]
        if blocking:
            return {"ok": False, "error": "fix these problems first", "issues": blocking}
        return {"ok": True, **on_finish(session)}
