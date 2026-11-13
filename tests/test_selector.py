from dataclasses import replace

import pandas as pd
import pytest

from config import settings as cfg
from mastery.profile import SkillState, StudentProfile
from placement.form import PlacementForm
from worksheets.blueprint import Slot, blueprint
from worksheets.selector import WorksheetPlan, plan_worksheet, split_equally, update_window

from .conftest import NOW, navigator_from

M = SkillState(mastery=0.99, mastered_at=NOW, flags=frozenset({cfg.FLAG_PLACEMENT}))
GAP = SkillState(mastery=0.2, flags=frozenset({cfg.FLAG_GAP}))


W = frozenset({cfg.FLAG_WINDOW})


def nav_of(topics, hard):
    """topics: {id: topic}; hard: [(skill, prerequisite)]."""
    skills = pd.DataFrame([(i, t, None, f"s{i}") for i, t in topics.items()],
                          columns=["id", "topic", "sub_topic", "skill"])
    prereqs = pd.DataFrame([(s, p, "hard") for s, p in hard], columns=["skill_id", "prerequisite_id", "type"])
    return navigator_from(skills, prereqs)


@pytest.fixture
def fan_nav():
    """1 -> 2, 3, 4, 5 (hard);  4 -> 6 (hard)."""
    return nav_of({i: "A" for i in range(1, 7)}, [(2, 1), (3, 1), (4, 1), (5, 1), (6, 4)])


def window_of(nav, profile):
    return update_window(nav, profile)[0]


def test_split_equally():
    assert split_equally([7, 8, 9], 15) == {7: 5, 8: 5, 9: 5}
    assert split_equally([7, 8], 15) == {7: 8, 8: 7}
    assert split_equally([], 15) == {}


def test_empty_window_fills_with_gaps_first_then_lowest_id(fan_nav):
    window, updates = update_window(fan_nav, StudentProfile(1, {1: M, 4: GAP, 5: GAP}))
    assert window == [4, 5, 2]
    assert all(cfg.FLAG_WINDOW in updates[s].flags for s in window)
    assert cfg.FLAG_GAP in updates[4].flags                  # other flags kept


def test_gap_not_ready_is_skipped_until_its_prerequisites_are_mastered(fan_nav):
    profile = StudentProfile(1, {1: M, 6: GAP})        # 6 needs 4
    assert 6 not in window_of(fan_nav, profile)
    assert window_of(fan_nav, profile.with_states({4: M}))[0] == 6


def test_window_nodes_stay_until_mastered(fan_nav):
    win = SkillState(flags=W)
    profile = StudentProfile(1, {1: M, 3: win, 4: win, 5: win, 2: GAP})   # a gap appears: nobody is pushed out
    window, updates = update_window(fan_nav, profile)
    assert window == [3, 4, 5] and updates == {}


def test_mastered_node_leaves_and_its_topic_continues():
    # 10 (topic B) is mastered and unlocks 5 (topic A) and 11 (topic B): stay on the B track
    nav = nav_of({7: "C", 8: "C", 10: "B", 11: "B", 5: "A"}, [(11, 10), (5, 10)])
    win = SkillState(flags=W)
    profile = StudentProfile(1, {7: win, 8: win, 10: replace(M, flags=W)})
    window, updates = update_window(nav, profile)
    assert window == [7, 8, 11]
    assert cfg.FLAG_WINDOW not in updates[10].flags


def test_topic_finished_switches_to_lowest_topic_number():
    # 10 is its topic's last node (like a Gate): 5 (lowest id) comes in
    nav = nav_of({7: "C", 8: "C", 10: "B", 30: "D", 5: "A"}, [(30, 10), (5, 10)])
    win = SkillState(flags=W)
    profile = StudentProfile(1, {7: win, 8: win, 10: replace(M, flags=W)})
    assert window_of(nav, profile) == [7, 8, 5]


def test_practice_sheet_is_the_window_split_equally(fan_nav):
    plan = plan_worksheet(fan_nav, StudentProfile(1, {1: M, 4: GAP, 5: GAP}))
    assert plan.kind == "practice" and plan.skill_counts == {4: 5, 5: 5, 2: 5}
    assert set(plan.state_updates) == {4, 5, 2}


def test_new_student_gets_a_placement_round(small_nav):
    plan = plan_worksheet(small_nav, StudentProfile(1), form=PlacementForm({"A": "partly"}))
    # the entry checkpoint first, then look-ahead behind it
    assert plan.kind == "placement" and list(plan.skill_counts)[0] == 3
    assert set(plan.skill_counts) <= {1, 2, 3}


def test_blueprint_gives_node_and_difficulty_per_question(small_nav):
    profile = StudentProfile(1, {2: SkillState(difficulty=2)})
    slots = blueprint(small_nav, profile, WorksheetPlan("practice", {2: 4, 1: 2}))
    # prerequisites first; node 2 at level 2 -> 30% easy, rest medium
    assert slots == [Slot(1, 1)] * 2 + [Slot(2, 1)] + [Slot(2, 2)] * 3

    fixed = blueprint(small_nav, profile, WorksheetPlan("placement", {2: 2}, difficulty=2))
    assert fixed == [Slot(2, 2)] * 2
