# guided-intake

A small Python library for voice assistants that need to collect several details from a person over a few turns. This is often called slot filling.

You describe what you need once. The library then:

- keeps track of which answers are in,
- picks the next question,
- understands loosely spoken values such as "12 cm" or "4 inches",
- runs your rules across the answers, and
- exposes all of it as MCP tools, so any agent can drive it.

## Why it exists

When an assistant collects details only through its prompt, it tends to forget a field, accept a value that cannot work, or ask in a confusing order. Here that logic is plain code, so you can test it. The language model only has to talk to the person and pass answers along.

## Install

The core has no dependencies:

```
pip install -e .
```

To use the MCP tools (needs the MCP Python SDK 2.x):

```
pip install -e ".[mcp]"
```

## Example in plain Python

`examples/tray.py` runs a short scripted conversation:

```
python examples/tray.py
```

The core pieces:

```python
from guided_intake import Check, Field, Issue, SessionStore, Spec

spec = Spec(
    name="tray", title="Tray", description="A shallow tray.",
    fields=(
        Field("width", "How wide?", unit="mm", minimum=10, maximum=300),
        Field("wall", "Wall thickness?", unit="mm", default=2.0),
        Field("lid", "Do you want a lid?", kind="bool"),
        Field("lid_fit", "Snug or loose?", kind="choice", choices=("snug", "loose"),
              active_when=lambda a: a.get("lid") is True),
    ),
    checks=(Check("thick", ("width", "wall"), lambda a: [] if a["wall"] * 2 < a["width"]
                  else [Issue("error", "The walls leave no room.")]),),
)

session = SessionStore([spec]).create("tray")
session.next_field().question        # "How wide?"
session.set_value("width", "12 cm")  # stored as 120.0 (millimeters)
session.is_complete()                # False, "lid" is still open
```

## Example as an MCP server

```python
from mcp.server.mcpserver import MCPServer
from guided_intake import SessionStore
from guided_intake.mcp_tools import register_intake_tools

server = MCPServer("my-intake")
store = SessionStore([spec])
register_intake_tools(server, store, on_finish=lambda s: {"summary": f"Saved {s.answers()}"})
server.run("streamable-http")
```

| Tool | What it does |
| --- | --- |
| `list_specs` | Lists the things this server can collect details for. |
| `start_intake` | Starts a session and returns the first question. |
| `submit_answers` | Saves one or more answers and returns the next question. |
| `review` | Returns the current question, collected answers and rule problems. |
| `finish` | Runs your `on_finish` function once everything is answered and no rule reports an error. |

Tools do not raise for bad user input. They return `{"ok": false, "error": "..."}` with wording an assistant can read out loud.

## Behavior to know about

- **Field kinds:** `number`, `choice`, `text`, `bool`.
- **Defaults:** a field with a default is never asked. The person can still set it.
- **Conditional fields:** `active_when` receives the answers collected so far. Answers for fields that stop being relevant are dropped.
- **Units:** for fields with `unit="mm"`, the values mm, cm, m and in (inch, inches) are converted. Number words such as "twelve" are not parsed, so the agent should convert them to digits.
- **Choices:** exact match ignoring case, or a unique prefix.
- **Rules:** a `Check` runs only when every field in `needs` has a value. An `error` blocks `finish`. A `warning` is reported but does not block.
- **Changing an answer:** `session.clear(name)` forgets an answer so the field is asked again.
- **Hints:** `Field(hint=...)` is extra context for the assistant, shown in the question details. It is never required and never asked.
- **Sessions:** kept in memory. The oldest are dropped after 500. Nothing is saved to disk. Creating and looking up sessions is thread safe. A single session is not, so do not share one between threads.

## Tests

```
pip install -e ".[dev]"
pytest
```

## Limits

- In-memory sessions only.
- English error messages.
- No authentication on the MCP tools. Put it behind your own auth if you expose it.

## License

MIT. See `LICENSE`.
