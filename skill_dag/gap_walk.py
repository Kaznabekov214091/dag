from collections import deque
from dataclasses import dataclass

from mastery.profile import UNKNOWN, WEAK


@dataclass(frozen=True)
class GapWalk:
    passed: frozenset[int]
    failed: frozenset[int]
    pending: tuple[int, ...]   # reached but unknown: assess these next
    gaps: tuple[int, ...]      # failed skills whose prerequisites all passed: fix these first

    @property
    def done(self):
        return not self.pending


def gap_walk(G, profile, start_skills, results=None):
    """Backward walk from `start_skills` over prerequisite graph `G`.

    Each skill is settled by `results` ({skill_id: passed}, from assessments) or else by the
    profile (weak -> failed; learning/mastered -> passed). A failed skill opens its prerequisites;
    a passed one stops the walk there. Unknown skills are returned as `pending`.
    Stateless: replaying the same results always gives the same walk.
    """
    results = results or {}
    passed, failed, pending = set(), set(), []
    queue = deque(sorted(set(start_skills)))
    seen = set(queue)

    while queue:
        skill = queue.popleft()
        if skill in results:
            ok = results[skill]
        elif profile.status(skill) == UNKNOWN:
            pending.append(skill)
            continue
        else:
            ok = profile.status(skill) != WEAK

        if ok:
            passed.add(skill)
            continue
        failed.add(skill)
        for prereq in sorted(G.predecessors(skill)):
            if prereq not in seen:
                seen.add(prereq)
                queue.append(prereq)

    gaps = sorted(s for s in failed if all(p in passed for p in G.predecessors(s)))
    return GapWalk(frozenset(passed), frozenset(failed), tuple(pending), tuple(gaps))
