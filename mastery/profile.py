from dataclasses import dataclass, field, replace
from datetime import datetime

from config import settings as cfg

MASTERED = "mastered"   # mastered_at is set (hard level passed, placement, or a teacher)
LEARNING = "learning"   # in between
WEAK = "weak"           # mastery < WEAK_BELOW
UNKNOWN = "unknown"     # no row for this skill (e.g. a new student)


@dataclass(frozen=True)
class SkillState:
    """One row of student_mastery."""
    mastery: float = 0.5                     # overall rate; 0.5 = no answers yet (see mastery.rate)
    difficulty: int = cfg.LEVELS[0]          # current level on this node
    mastered_at: datetime | None = None
    next_review_at: datetime | None = None
    review_level: int = 0
    flags: frozenset[str] = frozenset()

    @property
    def is_mastered(self):
        return self.mastered_at is not None

    def is_due(self, now):
        return self.next_review_at is not None and self.next_review_at <= now


@dataclass(frozen=True)
class StudentProfile:
    student_id: int
    skills: dict[int, SkillState] = field(default_factory=dict)

    @property
    def mastered(self):
        return frozenset(s for s, st in self.skills.items() if st.is_mastered)

    @property
    def placed(self):
        """Placement is finished once any row carries the placement flag."""
        return any(cfg.FLAG_PLACEMENT in st.flags for st in self.skills.values())

    def mastery(self, skill_id):
        st = self.skills.get(skill_id)
        return st.mastery if st else None

    def level(self, skill_id):
        st = self.skills.get(skill_id)
        return st.difficulty if st else cfg.LEVELS[0]

    def status(self, skill_id):
        st = self.skills.get(skill_id)
        if st is None:
            return UNKNOWN
        if st.is_mastered:
            return MASTERED
        return WEAK if st.mastery < cfg.WEAK_BELOW else LEARNING

    def flagged(self, flag):
        return sorted(s for s, st in self.skills.items() if flag in st.flags)

    def due_reviews(self, now):
        due = [s for s, st in self.skills.items() if st.is_mastered and st.is_due(now)]
        return sorted(due, key=lambda s: (self.skills[s].next_review_at, s))

    def with_states(self, updates):
        return replace(self, skills={**self.skills, **updates})
