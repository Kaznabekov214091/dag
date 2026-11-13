import pandas as pd

from importer.checks import run_all
from mastery.profile import SkillState, StudentProfile

from .conftest import NOW

M = SkillState(mastery=1.0, mastered_at=NOW)   # mastered
W = SkillState(mastery=0.1)    # weak


def test_skill_without_hard_prerequisites_falls_back_to_soft(small_nav):
    assert set(small_nav.prerequisites.predecessors(11)) == {3}
    assert small_nav.roots() == [1]


def test_gap_walk_stops_at_known_skills_and_reports_unknown(small_nav):
    profile = StudentProfile(1, {12: W, 11: M})
    walk = small_nav.gap_walk(profile, [13], {13: False})
    assert walk.failed == {13, 12}
    assert walk.passed == {11}
    assert walk.gaps == (12,)
    assert walk.pending == ()


def test_gap_walk_returns_unknown_skills_to_assess(small_nav):
    walk = small_nav.gap_walk(StudentProfile(1), [13], {13: False})
    assert set(walk.pending) == {11, 12}
    assert not walk.done


def test_gap_walk_is_replayable_from_results(small_nav):
    results = {13: False, 12: False, 11: True}
    walk = small_nav.gap_walk(StudentProfile(1), [13], results)
    assert walk.done and walk.gaps == (12,)


def test_forward_next_skills_and_path(small_nav):
    profile = StudentProfile(1, {1: M, 2: M, 3: M})
    assert small_nav.next_skills(profile) == [11]
    assert small_nav.path_to(profile, 13) == [11, 12, 13]


def test_prerequisites_within_depth(small_nav):
    assert small_nav.prerequisites_within([22], 1) == {21: 1, 12: 1}
    assert small_nav.prerequisites_within([22], 2) == {21: 1, 12: 1, 13: 2, 11: 2}


def test_topics_in_curriculum_order(small_nav):
    assert small_nav.topics() == ["A", "B", "C"]


def test_import_checks_reject_a_cycle():
    skills = pd.DataFrame([(1, "A", None, "x"), (2, "A", None, "y")], columns=["id", "topic", "sub_topic", "skill"])
    prereqs = pd.DataFrame([(2, 1, "hard"), (1, 2, "hard")], columns=["skill_id", "prerequisite_id", "type"])
    issues = run_all(skills, prereqs)
    assert "cycle" in set(issues.loc[issues["severity"] == "error", "check"])
