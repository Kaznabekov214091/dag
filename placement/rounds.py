"""Placement on paper: a backward gap walk inside a window, run in worksheet rounds.

Nothing extra is stored. The state is rebuilt from the student's graded worksheets: while a
student is not placed, every graded worksheet is a placement round. The window comes from the
questionnaire for round 1; later rounds recover its end skills from round 1 (its outermost skills).
"""
from dataclasses import dataclass
import networkx as nx

from config import settings as cfg
from mastery import rate
from mastery.apply import scores_by_skill
from mastery.profile import UNKNOWN, SkillState
from mastery.reviews import next_review

from .form import PlacementForm, Window, outermost, placement_window, window_skills


@dataclass(frozen=True)
class PlacementState:
    window: Window
    walk: object           # skill_dag.gap_walk.GapWalk
    rounds_done: int
    scores: dict           # {skill_id: [scores]} from all rounds together

    @property
    def finished(self):
        return self.rounds_done > 0 and (self.walk.done or self.rounds_done >= cfg.PLACEMENT_MAX_ROUNDS)


def placement_state(navigator, profile, graded_rounds, form=None):
    """`graded_rounds`: the student's graded worksheets, oldest first, each [(skill_id, score), ...]."""
    if graded_rounds:
        # round 1 = end skills + window skills behind them, so the end skills are the outermost ones
        end = outermost(navigator, {skill for skill, _ in graded_rounds[0]})
        window = Window(tuple(end), window_skills(navigator, end))
    else:
        window = placement_window(navigator, form or PlacementForm())

    scores = {}
    for round_items in graded_rounds:
        for skill, s in scores_by_skill(round_items).items():
            scores.setdefault(skill, []).extend(s)
    # confidence: a skill is settled only when its smoothed rate is clearly high or clearly low;
    # in between it stays pending and is asked again next round
    results = {skill: verdict for skill, s in scores.items() if (verdict := placement_verdict(s)) is not None}

    walk = navigator.gap_walk(profile, window.end, results)
    return PlacementState(window, walk, len(graded_rounds), scores)


def placement_verdict(scores):
    """True = clearly passed, False = clearly failed, None = not sure yet (smoothed rate in between)."""
    r = rate.rate(scores)
    if r >= cfg.PLACEMENT_PASS_RATE:
        return True
    if r <= cfg.PLACEMENT_FAIL_RATE:
        return False
    return None


def beginner_states(navigator):
    """A beginner is not tested: they start at the roots of the DAG (flag placement = placed)."""
    return {root: SkillState(flags=frozenset({cfg.FLAG_PLACEMENT})) for root in navigator.roots()}


def next_round(navigator, profile, state, num_questions):
    """{skill_id: question count} for the next placement worksheet.

    The pending skills come first (round 1: every end skill, so they can be read back later).
    Spare room is filled by looking ahead at the unknown skills behind them, closest first. The
    look-ahead stays inside the window; only once the walk itself has gone below the window (the
    lower bound moved) does it look ahead from there.
    """
    qps = cfg.PLACEMENT_QUESTIONS_PER_SKILL
    cap = min(cfg.PLACEMENT_MAX_SKILLS_PER_ROUND, max(1, num_questions // qps))
    pending = list(state.walk.pending)
    skills = pending if state.rounds_done == 0 else pending[:cap]
    for skill in look_ahead(navigator, skills, state.window.skills, cap):
        if len(skills) >= cap:
            break
        if skill not in skills and skill not in state.scores and profile.status(skill) == UNKNOWN:
            skills.append(skill)
    return {skill: qps for skill in skills}


def look_ahead(navigator, skills, window, depth):
    """Skills behind `skills`, closest first: inside the window for skills in it, free below it."""
    inside = [s for s in skills if s in window]
    below = [s for s in skills if s not in window]
    found = {s: d for s, d in navigator.prerequisites_within(inside, depth).items() if s in window}
    for s, d in navigator.prerequisites_within(below, depth).items():
        found[s] = min(d, found.get(s, d))
    return sorted(found, key=lambda s: (found[s], s))


def finish(navigator, profile, state, now):
    """Mastery rows that close placement: {skill_id: SkillState}.

    passed  -> mastered at the top level (flag placement), reviews scheduled
    failed  -> level 1, mastery from its scores (flag placement, plus gap for the deepest failures)
    inferred-> skills behind a passed skill, still unknown: mastered (flag inferred), no reviews
    """
    updates, passed = {}, set(state.walk.passed)
    for skill, scores in state.scores.items():
        if placement_verdict(scores):     # look-ahead skills the walk never reached count too
            passed.add(skill)
            updates[skill] = SkillState(
                mastery=1.0, difficulty=rate.TOP_LEVEL, mastered_at=now, next_review_at=next_review(0, now),
                flags=frozenset({cfg.FLAG_PLACEMENT}),
            )
        else:
            flags = {cfg.FLAG_PLACEMENT} | ({cfg.FLAG_GAP} if skill in state.walk.gaps else set())
            history = [(cfg.PLACEMENT_DIFFICULTY, score) for score in scores]
            updates[skill] = SkillState(mastery=rate.overall(history), difficulty=cfg.LEVELS[0], flags=frozenset(flags))

    for skill in passed:
        for prereq in nx.ancestors(navigator.prerequisites, skill):
            if (prereq not in updates and prereq not in state.walk.failed
                    and profile.status(prereq) == UNKNOWN):
                updates[prereq] = SkillState(
                    mastery=1.0, difficulty=rate.TOP_LEVEL, mastered_at=now, flags=frozenset({cfg.FLAG_INFERRED}),
                )
    return updates
