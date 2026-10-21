"""Smallest useful example: a tray spec, a rule, and a short scripted conversation."""
from guided_intake import Check, Field, Issue, SessionStore, Spec


def walls_leave_room(answers):
    if answers["wall"] * 2 >= min(answers["width"], answers["depth"]):
        return [Issue("error", "The walls leave no room inside.", ("wall",), "Use thinner walls.")]
    return []


TRAY = Spec(
    name="tray",
    title="Tray",
    description="A shallow tray.",
    fields=(
        Field("width", "How wide?", unit="mm", minimum=10, maximum=300),
        Field("depth", "How deep?", unit="mm", minimum=10, maximum=300),
        Field("wall", "How thick should the walls be?", unit="mm", minimum=0.8, maximum=10, default=2.0),
        Field("lid", "Do you want a lid?", kind="bool"),
        Field("lid_fit", "Snug or loose?", kind="choice", choices=("snug", "loose"),
              active_when=lambda a: a.get("lid") is True),
    ),
    checks=(Check("walls", ("width", "depth", "wall"), walls_leave_room),),
)

if __name__ == "__main__":
    session = SessionStore([TRAY]).create("tray")
    for field_name, spoken in [("width", "12 cm"), ("depth", "8 cm"), ("lid", "yes"), ("lid_fit", "snug")]:
        asked = session.next_field()
        print(f"asked: {asked.question}")
        print(f"heard: {spoken!r} for {field_name}")
        print(" ->", session.set_value(field_name, spoken).to_dict())
    print("complete:", session.is_complete(), "| can finish:", session.can_finish())
    print("answers:", session.answers())
