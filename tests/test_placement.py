import networkx as nx

from config import settings as cfg
from mastery.profile import MASTERED, StudentProfile
from placement.form import PARTLY, WELL, PlacementForm, placement_window
from placement.rounds import beginner_states, finish, next_round, placement_state, placement_verdict

from .conftest import NOW


def run_placement(nav, knows, form, num_questions=10):
    """Simulate paper rounds for a student who passes exactly the skills `knows` accepts."""
    profile, rounds, sheets = StudentProfile(1), [], []
    while True:
        state = placement_state(nav, profile, rounds, form)
        if state.finished:
            return state, profile.with_states(finish(nav, profile, state, NOW)), sheets
        counts = next_round(nav, profile, state, num_questions)
        sheets.append(set(counts))
        rounds.append([(s, 1.0 if knows(s) else 0.0) for s, n in counts.items() for _ in range(n)])


# small_nav (hard prerequisites): 1 -> 2 -> 3(Gate A);  11 -> 12 -> 13(Gate B), 11 -> 13;  13 -> 21 -> 22, 12 -> 22


def test_nothing_known_is_a_beginner_without_a_test(small_nav):
    assert placement_window(small_nav, PlacementForm()).beginner
    assert placement_window(small_nav, PlacementForm({"A": "dont_know"})).beginner
    profile = StudentProfile(1).with_states(beginner_states(small_nav))
    assert profile.placed and set(profile.skills) == set(small_nav.roots())
    assert small_nav.next_skills(profile)[0] == 1


def test_window_is_end_plus_two_levels_and_stops_at_start(small_nav):
    w = placement_window(small_nav, PlacementForm({"B": PARTLY}))
    assert w.end == (13,) and w.skills == {13, 12, 11, 3}          # 2 levels below the Gate of B
    assert placement_window(small_nav, PlacementForm({"C": PARTLY})).skills == {22, 21, 13, 12, 11}
    w = placement_window(small_nav, PlacementForm({"B": WELL, "C": PARTLY}))
    assert w.end == (22,) and w.skills == {22, 21, 13}             # B's Gate is start: nothing behind it
    w = placement_window(small_nav, PlacementForm({"A": PARTLY, "C": PARTLY}))
    assert w.end == (22,)                                          # A's Gate lies behind C's end


def test_round_one_stays_inside_the_window(algebra_nav):
    topics = algebra_nav.topics()
    form = PlacementForm({topics[7]: PARTLY})
    window = placement_window(algebra_nav, form)
    state = placement_state(algebra_nav, StudentProfile(1), [], form)
    counts = next_round(algebra_nav, StudentProfile(1), state, num_questions=40)
    assert set(window.end) <= set(counts) <= window.skills


def test_finds_the_gap_and_infers_the_rest(small_nav):
    # lacks 12, so also fails 13 which needs it
    state, profile, _ = run_placement(small_nav, knows=lambda s: s not in (12, 13), form=PlacementForm({"B": PARTLY}))
    assert state.walk.gaps == (12,)
    assert cfg.FLAG_GAP in profile.skills[12].flags
    assert profile.status(11) == MASTERED
    inferred = profile.flagged(cfg.FLAG_INFERRED)
    assert all(s not in state.scores and profile.skills[s].next_review_at is None for s in inferred)
    assert set(inferred) | set(state.scores) == {1, 2, 3, 11, 12, 13}


def test_lower_bound_moves_below_the_window(algebra_nav):
    G = algebra_nav.prerequisites
    form = PlacementForm({algebra_nav.topics()[7]: PARTLY})
    window = placement_window(algebra_nav, form)
    # the student lacks a skill deep below the window, and so fails everything built on it
    deep = next(s for s in nx.ancestors(G, window.end[0]) - window.skills
                if algebra_nav.prerequisites.in_degree(s) > 0)
    missing = {deep} | nx.descendants(G, deep)
    state, profile, _ = run_placement(algebra_nav, knows=lambda s: s not in missing, form=form, num_questions=40)
    assert deep not in window.skills
    assert state.walk.done and state.walk.gaps == (deep,) and cfg.FLAG_GAP in profile.skills[deep].flags


def test_placement_stops_after_max_rounds(algebra_nav):
    form = PlacementForm({t: PARTLY for t in algebra_nav.topics()[:12]})
    state, profile, sheets = run_placement(algebra_nav, knows=lambda s: s < 500, form=form)
    assert state.rounds_done <= cfg.PLACEMENT_MAX_ROUNDS and len(sheets) == state.rounds_done
    assert profile.placed


def test_real_curriculum_finds_the_known_gap(algebra_nav):
    G = algebra_nav.prerequisites
    missing = {302} | nx.descendants(G, 302)            # lacks 302 and everything built on it
    form = PlacementForm({t: PARTLY for t in algebra_nav.topics()[:4]})
    state, profile, _ = run_placement(algebra_nav, knows=lambda s: s not in missing, form=form, num_questions=40)
    assert state.walk.done and state.walk.gaps == (302,)
    assert all(profile.status(s) == MASTERED for s in state.walk.passed)


def test_unclear_skill_is_asked_again():
    assert placement_verdict([1, 1]) is True                  # 3/4 = 0.75
    assert placement_verdict([0, 0]) is False                 # 1/4 = 0.25
    assert placement_verdict([1, 0]) is None                  # 2/4 = 0.5: not sure
    assert placement_verdict([1, 0, 1, 1]) is None            # 4/6 = 0.67
    assert placement_verdict([1, 0, 0, 0]) is False           # 2/6 = 0.33


def test_half_right_keeps_the_skill_pending(small_nav):
    form = PlacementForm({"B": PARTLY})
    state = placement_state(small_nav, StudentProfile(1), [[(13, 1), (13, 0)]], form)
    assert 13 in state.walk.pending and not state.finished
    state = placement_state(small_nav, StudentProfile(1), [[(13, 1), (13, 0)], [(13, 1), (13, 1), (13, 1), (13, 1)]], form)
    assert 13 in state.walk.passed                            # 5 of 6 -> 6/8 = 0.75
