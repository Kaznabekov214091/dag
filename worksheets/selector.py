"""Decides WHAT goes on one student's worksheet: {skill_id: question count}."""
from dataclasses import dataclass

from config import settings as cfg
from mastery.profile import MASTERED
from placement.rounds import next_round, placement_state


@dataclass(frozen=True)
class WorksheetPlan:
    kind: str                   # "placement" | "practice"
    skill_counts: dict          # {skill_id: number of questions}
    difficulty: int | None = None   # fixed difficulty (placement), None -> each node's level mix


def plan_worksheet(navigator, profile, settings, graded_rounds=(), form=None, now=None):
    """A beginner (questionnaire: nothing known) must already have been given beginner_states."""
    if not profile.placed:
        state = placement_state(navigator, profile, list(graded_rounds), form)
        if state.window.beginner:
            raise ValueError("beginner: write placement.rounds.beginner_states first")
        if not state.finished:
            return WorksheetPlan("placement", next_round(navigator, profile, state, settings.num_questions),
                                 cfg.PLACEMENT_DIFFICULTY)

    if settings.target_node_ids:
        skills = targeted_skills(navigator, profile, settings)
        return WorksheetPlan("practice", fill(skills, settings.num_questions))

    groups = practice_groups(navigator, profile, now)
    return WorksheetPlan("practice", allocate(groups, settings.num_questions, cfg.WORKSHEET_MIX))


# ---------------------------------------------------------
# Teacher picked target skills
# ---------------------------------------------------------
def targeted_skills(navigator, profile, settings):
    """Targets first, then weak earlier skills within max_depth (weakest first)."""
    targets = list(dict.fromkeys(settings.target_node_ids))
    if not settings.include_weak_prereqs:
        return targets
    within = navigator.prerequisites_within(targets, settings.max_depth)
    mastery = lambda s: profile.mastery(s) or 0.0
    weak = sorted((s for s in within if mastery(s) < settings.weak_below), key=lambda s: (mastery(s), s))
    return targets + weak


# ---------------------------------------------------------
# System picks: gaps -> next skills -> reviews
# ---------------------------------------------------------
def practice_groups(navigator, profile, now):
    gaps = []
    for skill in profile.flagged(cfg.FLAG_STUCK):
        walk = navigator.gap_walk(profile, [skill], {skill: False})
        gaps += list(walk.pending) + list(walk.gaps)   # probe unknown prerequisites, practise found gaps
    gaps += [s for s in profile.flagged(cfg.FLAG_GAP) if profile.status(s) != MASTERED]
    gaps = list(dict.fromkeys(gaps))

    taken = set(gaps)
    nxt = [s for s in navigator.next_skills(profile) if s not in taken]
    taken.update(nxt)
    review = [s for s in profile.due_reviews(now) if s not in taken] if now else []
    return {"gaps": gaps, "next": nxt, "review": review}


def allocate(groups, num_questions, shares):
    """Split questions over the non-empty groups by share, then fill each group's skills."""
    active = [g for g in shares if groups.get(g)]
    if not active:
        return {}
    total = sum(shares[g] for g in active)
    quotas = {g: int(num_questions * shares[g] / total) for g in active}
    for g in active[: num_questions - sum(quotas.values())]:
        quotas[g] += 1

    counts = {}
    for g in active:
        for skill, n in fill(groups[g], quotas[g]).items():
            counts[skill] = counts.get(skill, 0) + n
    return counts


def fill(skills, num_questions, per_skill=cfg.QUESTIONS_PER_SKILL):
    """Give skills (in priority order) `per_skill` questions each, then spread what is left one by one."""
    counts, left = {}, num_questions
    for skill in skills:
        if left <= 0:
            break
        counts[skill] = min(per_skill, left)
        left -= counts[skill]
    while left > 0 and counts:
        for skill in list(counts):
            if left <= 0:
                break
            counts[skill] += 1
            left -= 1
    return counts
