from dataclasses import replace
from statistics import mean

from config import settings as cfg

from . import rate
from .profile import SkillState
from .reviews import next_review


def scores_by_skill(items):
    """[(skill_id, score), ...] in worksheet order -> {skill_id: [scores]}."""
    grouped = {}
    for skill_id, score in items:
        grouped.setdefault(skill_id, []).append(score)
    return grouped


def apply_practice(profile, items, histories, now):
    """Mastery updates from a graded practice worksheet: {skill_id: new SkillState}.

    `items`: this worksheet, [(skill_id, score), ...].
    `histories`: {skill_id: [(difficulty, score), ...]} every graded answer, oldest first, this worksheet included.
    """
    return {
        skill: update_skill(profile.skills.get(skill, SkillState()), histories.get(skill, []), scores, now)
        for skill, scores in scores_by_skill(items).items()
    }


def update_skill(old, history, sheet_scores, now):
    """Levels only go up; mastered = the top level passed. A mastered skill stays mastered (reviews only)."""
    flags = set(old.flags)

    if old.is_mastered:
        state = old
        if old.is_due(now):
            if mean(sheet_scores) >= cfg.PASS_SCORE:
                flags.discard(cfg.FLAG_REVIEW_FAILED)
                level = old.review_level + 1
            else:
                flags.add(cfg.FLAG_REVIEW_FAILED)
                level = 0
            state = replace(state, review_level=level, next_review_at=next_review(level, now))
        return replace(state, flags=frozenset(flags))

    level = rate.next_level(history, old.difficulty)
    if level == rate.TOP_LEVEL and rate.passed_level(history, level):
        flags -= {cfg.FLAG_GAP, cfg.FLAG_STUCK}
        return replace(old, mastery=1.0, difficulty=level, mastered_at=now, review_level=0,
                       next_review_at=next_review(0, now), flags=frozenset(flags))

    if rate.is_stuck(history, level):
        flags.add(cfg.FLAG_STUCK)
    else:
        flags.discard(cfg.FLAG_STUCK)
    return replace(old, mastery=rate.overall(history), difficulty=level, flags=frozenset(flags))
