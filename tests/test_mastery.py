from datetime import timedelta

from config import settings as cfg
from mastery import rate
from mastery.apply import apply_practice, update_skill
from mastery.profile import SkillState, StudentProfile

from .conftest import NOW


def test_smoothed_rate():
    assert rate.rate([]) == 0.5
    assert rate.rate([1]) == 2 / 3                          # one lucky answer is not 100%
    assert rate.rate([1] * 9 + [0]) == 10 / 12
    assert len(rate.recent([(1, 1)] * 30, 1)) == cfg.RATE_WINDOW


def test_level_goes_up_after_enough_good_answers():
    assert rate.next_level([(1, 1)] * 9, 1) == 1            # too few answers
    assert rate.next_level([(1, 1)] * 8 + [(1, 0)] * 2, 1) == 1   # 9/12 = 75% < 80%
    assert rate.next_level([(1, 1)] * 9 + [(1, 0)], 1) == 2       # 10/12 = 83%


def test_mix_uses_only_the_level_below():
    assert rate.level_mix(1, 4) == {1: 4}
    assert rate.level_mix(2, 4) == {1: 1, 2: 3}
    assert rate.level_mix(3, 10) == {2: 3, 3: 7}
    assert rate.level_mix(3, 1) == {3: 1}


def test_practice_moves_level_up_then_masters_at_the_top():
    st = update_skill(SkillState(), [(1, 1)] * 10, [1] * 10, NOW)
    assert st.difficulty == 2 and not st.is_mastered
    history = [(1, 1)] * 10 + [(2, 1)] * 10 + [(3, 1)] * 10
    st = update_skill(SkillState(difficulty=3, flags=frozenset({cfg.FLAG_GAP})), history, [1] * 10, NOW)
    assert st.is_mastered and st.mastered_at == NOW and st.mastery == 1.0
    assert cfg.FLAG_GAP not in st.flags
    assert st.next_review_at == NOW + timedelta(days=cfg.REVIEW_INTERVALS_DAYS[0])


def test_level_never_goes_down_in_practice():
    st = update_skill(SkillState(difficulty=2), [(2, 0)] * 10, [0] * 10, NOW)
    assert st.difficulty == 2


def test_low_rate_at_the_current_level_makes_a_skill_stuck():
    st = update_skill(SkillState(), [(1, 0)] * 4, [0] * 4, NOW)
    assert cfg.FLAG_STUCK not in st.flags                   # fewer than STUCK_MIN_ANSWERS
    st = update_skill(st, [(1, 0)] * 5, [0], NOW)
    assert cfg.FLAG_STUCK in st.flags
    st = update_skill(st, [(1, 0)] * 5 + [(1, 1)] * 6, [1] * 6, NOW)
    assert cfg.FLAG_STUCK not in st.flags                   # 7/13 >= 50%


def test_reviews_keep_the_skill_mastered():
    due = SkillState(mastery=1.0, difficulty=3, mastered_at=NOW - timedelta(days=5),
                     next_review_at=NOW - timedelta(hours=1), review_level=1)
    st = update_skill(due, [], [1, 1], NOW)
    assert st.review_level == 2 and st.next_review_at == NOW + timedelta(days=cfg.REVIEW_INTERVALS_DAYS[2])
    st = update_skill(due, [], [0, 0], NOW)
    assert st.is_mastered and st.review_level == 0 and cfg.FLAG_REVIEW_FAILED in st.flags


def test_apply_practice_groups_items_by_skill():
    profile = StudentProfile(1, {5: SkillState()})
    history = {5: [(1, 1), (1, 1)], 6: [(1, 0)]}
    updates = apply_practice(profile, [(5, 1), (6, 0), (5, 1)], history, NOW)
    assert set(updates) == {5, 6}
    assert updates[5].mastery > 0.5 > updates[6].mastery

