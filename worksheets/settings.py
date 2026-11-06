from dataclasses import dataclass

from config import settings as cfg


@dataclass(frozen=True)
class WorksheetSettings:
    """What the teacher can tweak for an assignment (chosen in the UI, sent with the request)."""
    num_questions: int = cfg.DEFAULT_NUM_QUESTIONS
    target_node_ids: tuple[int, ...] = ()        # empty -> the system picks (gaps / next / reviews)
    include_weak_prereqs: bool = True            # False -> questions only from the target skills
    max_depth: int = cfg.DEFAULT_MAX_DEPTH       # how far back from the targets to look
    weak_below: float = cfg.WEAK_BELOW           # earlier skills below this mastery are added
