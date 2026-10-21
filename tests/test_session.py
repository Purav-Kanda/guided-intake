import pytest

from guided_intake import Check, Field, Issue, SessionStore, Spec, parse_number


def make_spec() -> Spec:
    def thin_walls(a):
        if a["wall"] * 2 >= min(a["width"], a["depth"]):
            return [Issue("error", "walls leave no room inside", ("wall",), "use a thinner wall")]
        return []

    return Spec(
        name="tray",
        title="Tray",
        description="a tray",
        fields=(
            Field("width", "How wide?", unit="mm", minimum=10, maximum=300),
            Field("depth", "How deep?", unit="mm", minimum=10, maximum=300),
            Field("wall", "Wall thickness?", unit="mm", minimum=0.8, maximum=10, default=2.0),
            Field("lid", "Want a lid?", kind="bool"),
            Field("lid_fit", "Snug or loose?", kind="choice", choices=("snug", "loose"),
                  active_when=lambda a: a.get("lid") is True),
        ),
        checks=(Check("walls", ("width", "depth", "wall"), thin_walls),),
    )


def test_unit_conversion_for_spoken_lengths():
    assert parse_number("12 cm", "mm") == 120.0
    assert parse_number("2 inches", "mm") == 50.8
    assert parse_number("85", "mm") == 85.0


def test_unit_mismatch_is_rejected():
    with pytest.raises(ValueError):
        parse_number("5 kg", "mm")


def test_questions_come_in_order_and_defaults_are_skipped():
    s = SessionStore([make_spec()]).create("tray")
    assert s.next_field().name == "width"
    s.set_value("width", "100")
    assert s.next_field().name == "depth"
    s.set_value("depth", "60")
    assert s.next_field().name == "lid"  # wall has a default, so it is not asked


def test_dependent_field_only_appears_when_relevant():
    s = SessionStore([make_spec()]).create("tray")
    s.set_many({"width": "100", "depth": "60", "lid": "no"})
    assert s.is_complete()
    s.set_value("lid", "yes")
    assert s.next_field().name == "lid_fit"
    s.set_value("lid_fit", "sn")  # unique prefix
    assert s.answers()["lid_fit"] == "snug"


def test_inactive_answers_are_dropped_from_collected():
    s = SessionStore([make_spec()]).create("tray")
    s.set_many({"width": "100", "depth": "60", "lid": "yes", "lid_fit": "loose"})
    s.set_value("lid", "no")
    assert "lid_fit" not in s.answers()


def test_out_of_range_and_unknown_fields_give_readable_errors():
    s = SessionStore([make_spec()]).create("tray")
    bad = s.set_value("width", "5")
    assert not bad.ok and "at least 10 mm" in bad.message
    assert "Known fields" in s.set_value("height", "5").message


def test_check_waits_for_its_inputs_then_blocks_finish():
    s = SessionStore([make_spec()]).create("tray")
    s.set_value("width", "15")
    assert s.issues() == []  # depth is missing, so the rule does not run yet
    s.set_many({"depth": "60", "wall": "9", "lid": "no"})
    assert [i.severity for i in s.issues()] == ["error"]
    assert not s.can_finish()
    s.set_value("wall", "3")
    assert s.can_finish()


def test_store_evicts_oldest_and_reports_unknown_ids():
    store = SessionStore([make_spec()], max_sessions=2)
    first = store.create("tray")
    store.create("tray")
    store.create("tray")
    with pytest.raises(KeyError):
        store.get(first.session_id)
    with pytest.raises(KeyError):
        store.create("nope")


def test_duplicate_field_names_are_rejected():
    with pytest.raises(ValueError):
        Spec("x", "x", "x", (Field("a", "?"), Field("a", "?")))


def test_hint_is_passed_to_the_assistant_but_not_required():
    plain = Field("a", "Question?")
    hinted = Field("b", "Question?", hint="Extra context for the assistant")
    assert "hint" not in plain.describe()
    assert hinted.describe()["hint"] == "Extra context for the assistant"


def test_store_stays_within_its_cap_under_many_threads():
    import threading

    store = SessionStore([make_spec()], max_sessions=50)
    workers = [threading.Thread(target=lambda: [store.create("tray") for _ in range(40)]) for _ in range(8)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    assert len(store._live) == 50


def test_clear_makes_a_field_be_asked_again():
    from guided_intake import Field, SessionStore, Spec

    spec = Spec(name="s", title="S", description="d", fields=(Field("w", "Width?", kind="number"),))
    s = SessionStore([spec]).create("s")
    s.set_value("w", "5")
    assert s.is_complete()
    assert s.clear("w") is True and s.next_field().name == "w"
    assert s.clear("w") is False


def test_progress_tells_the_assistant_what_to_do_next():
    s = SessionStore([make_spec()]).create("tray")
    assert "next_question" in s.progress()["next_step"]
    s.set_many({"width": "15", "depth": "60", "wall": "9", "lid": "no"})
    assert "fix the errors" in s.progress()["next_step"]
    s.set_value("wall", "3")
    assert "Call finish" in s.progress()["next_step"]
