from datetime import timedelta

from config import settings as cfg
from mastery.profile import SkillState, StudentProfile
from placement.form import PlacementForm
from worksheets.selector import allocate, fill, plan_worksheet, practice_groups
from worksheets.settings import WorksheetSettings

from .conftest import NOW

M = SkillState(mastery=0.99, mastered_at=NOW, flags=frozenset({cfg.FLAG_PLACEMENT}))


def test_fill_gives_each_skill_its_share_then_spreads():
    assert fill([1, 2, 3], 4) == {1: 2, 2: 2}
    assert fill([1], 5) == {1: 5}
    assert fill([1, 2], 7) == {1: 4, 2: 3}


def test_allocate_moves_empty_groups_share_to_others():
    counts = allocate({"gaps": [], "next": [5, 6], "review": [9]}, 10, cfg.WORKSHEET_MIX)
    assert sum(counts.values()) == 10 and 9 in counts


def test_new_student_gets_a_placement_round(small_nav):
    plan = plan_worksheet(small_nav, StudentProfile(1), WorksheetSettings(), form=PlacementForm({"A": "partly"}))
    # the entry checkpoint first, then look-ahead behind it
    assert plan.kind == "placement" and list(plan.skill_counts)[0] == 3
    assert set(plan.skill_counts) <= {1, 2, 3}


def test_teacher_targets_only_selected(small_nav):
    profile = StudentProfile(1, {1: M})
    plan = plan_worksheet(small_nav, profile, WorksheetSettings(6, (13,), include_weak_prereqs=False))
    assert plan.skill_counts == {13: 6}


def test_teacher_targets_with_weak_prerequisites_within_depth(small_nav):
    profile = StudentProfile(1, {1: M, 11: M, 12: SkillState(mastery=0.2)})
    plan = plan_worksheet(small_nav, profile, WorksheetSettings(6, (13,), max_depth=1))
    assert set(plan.skill_counts) == {13, 12}     # 11 is mastered, so not added


def test_stuck_skill_pulls_its_unknown_prerequisites_into_the_sheet(small_nav):
    stuck = SkillState(mastery=0.3, flags=frozenset({cfg.FLAG_STUCK}))
    profile = StudentProfile(1, {1: M, 2: M, 3: M, 13: stuck})
    groups = practice_groups(small_nav, profile, NOW)
    assert set(groups["gaps"]) == {11, 12}


def test_due_reviews_are_included(small_nav):
    due = SkillState(mastery=0.99, mastered_at=NOW - timedelta(days=3),
                     next_review_at=NOW - timedelta(days=1), flags=frozenset({cfg.FLAG_PLACEMENT}))
    profile = StudentProfile(1, {1: due})
    plan = plan_worksheet(small_nav, profile, WorksheetSettings(10), now=NOW)
    assert plan.kind == "practice" and 1 in plan.skill_counts and 2 in plan.skill_counts
