from dataclasses import dataclass, field

from config import settings as cfg

DONT_KNOW, PARTLY, WELL = "dont_know", "partly", "well"
ANSWERS = (DONT_KNOW, PARTLY, WELL)


@dataclass(frozen=True)
class PlacementForm:
    """Questionnaire answered on joining: {topic: dont_know | partly | well}. Missing topics = dont_know."""
    answers: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Window:
    """The part of the DAG placement tests. No end skills = beginner (no test, start at the roots)."""
    end: tuple[int, ...] = ()
    skills: frozenset[int] = frozenset()

    @property
    def beginner(self):
        return not self.end


def checkpoint(navigator, topic):
    """A topic's Gate skill, or its last skill when it has none."""
    skills = navigator.skills_in_topic(topic)
    if not skills:
        raise ValueError(f"unknown topic: {topic!r}")
    gates = [s for s in skills if navigator.node(s)["sub_topic"] == cfg.GATE_SUB_TOPIC]
    return max(gates or skills)


def outermost(navigator, skills):
    """Drop skills lying behind another one in the set."""
    skills = set(skills)
    return sorted(s for s in skills if not any(navigator.is_prerequisite(s, o) for o in skills))


def placement_window(navigator, form):
    """Questionnaire answers -> window.

    end   = checkpoints of the topics answered partly/well (the outermost ones)
    start = checkpoints of the topics answered well: what lies behind them is assumed solid
    window = end + prerequisites up to PLACEMENT_WINDOW_DEPTH levels below, not going behind start
    """
    for topic, answer in form.answers.items():
        if answer not in ANSWERS:
            raise ValueError(f"answer for {topic!r} must be one of {ANSWERS}, got {answer!r}")
    known = [t for t, a in form.answers.items() if a in (PARTLY, WELL)]
    if not known:
        return Window()
    end = outermost(navigator, [checkpoint(navigator, t) for t in known])
    start = [checkpoint(navigator, t) for t, a in form.answers.items() if a == WELL]
    return Window(tuple(end), window_skills(navigator, end, start))


def window_skills(navigator, end, start=()):
    below = navigator.prerequisites_within(end, cfg.PLACEMENT_WINDOW_DEPTH)
    below = [s for s in below if not any(navigator.is_prerequisite(s, st) for st in start)]
    return frozenset(end) | frozenset(below)
