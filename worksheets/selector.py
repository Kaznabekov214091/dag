"""Decides WHAT goes on one student's worksheet: {skill_id: question count}."""
from dataclasses import dataclass, field, replace

from config import settings as cfg
from mastery.profile import SkillState
from placement.rounds import next_round, placement_state


@dataclass(frozen=True)
class WorksheetPlan:
    kind: str                   # "placement" | "practice"
    skill_counts: dict          # {skill_id: number of questions}
    difficulty: int | None = None   # fixed difficulty (placement), None -> each node's level mix
    state_updates: dict = field(default_factory=dict)   # {skill_id: SkillState} to save (window flags)


def plan_worksheet(navigator, profile, graded_rounds=(), form=None):
    """A beginner (questionnaire: nothing known) must already have been given beginner_states."""
    if not profile.placed:
        state = placement_state(navigator, profile, list(graded_rounds), form)
        if state.window.beginner:
            raise ValueError("beginner: write placement.rounds.beginner_states first")
        if not state.finished:
            counts = next_round(navigator, profile, state, cfg.PLACEMENT_NUM_QUESTIONS)
            return WorksheetPlan("placement", counts, cfg.PLACEMENT_DIFFICULTY)

    window, updates = update_window(navigator, profile)
    return WorksheetPlan("practice", split_equally(window, cfg.PRACTICE_NUM_QUESTIONS), state_updates=updates)


def update_window(navigator, profile, size=cfg.WINDOW_SIZE):
    """The practice window (skills flagged `window`) after refilling it: (window, {skill_id: SkillState}).

    A node stays until it is mastered. A free place goes first to the next ready node in the same
    topic as the mastered node that left (continue the stream), then to the queue: ready gaps, then
    other ready nodes, lowest id (topic number) first. Ready = not mastered, every prerequisite mastered.
    """
    flagged = profile.flagged(cfg.FLAG_WINDOW)
    window = [s for s in flagged if s not in profile.mastered]
    left = [s for s in flagged if s in profile.mastered]

    ready = sorted(navigator.next_skills(profile))
    gaps = set(profile.flagged(cfg.FLAG_GAP))
    queue = [s for s in ready if s in gaps] + [s for s in ready if s not in gaps]
    topic = lambda s: navigator.node(s)["topic"]

    for gone in left:
        stream = [s for s in queue if topic(s) == topic(gone) and s not in window]
        if stream and len(window) < size:
            window.append(stream[0])
    for s in queue:
        if len(window) >= size:
            break
        if s not in window:
            window.append(s)

    updates = {s: replace(profile.skills[s], flags=profile.skills[s].flags - {cfg.FLAG_WINDOW}) for s in left}
    for s in window:
        if s not in flagged:
            old = profile.skills.get(s, SkillState())
            updates[s] = replace(old, flags=old.flags | {cfg.FLAG_WINDOW})
    return window, updates


def split_equally(nodes, num_questions):
    """{node: count}: the questions split equally; any remainder goes to the first nodes."""
    if not nodes:
        return {}
    each, extra = divmod(num_questions, len(nodes))
    return {node: each + (i < extra) for i, node in enumerate(nodes)}
