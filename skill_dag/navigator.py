import networkx as nx

from .gap_walk import gap_walk
from .graph import traversal
from .graph.builder import build_prerequisite_graph, check_dag


class SkillNavigator:
    """Forward/backward moves over the skill DAGs.

    prerequisites: hard edges, falling back to soft for skills with no hard ones
                   -> backward gap detection and what is unlocked going forward
    soft:          recommended curriculum order -> rank and order what to learn
    """

    def __init__(self, dags):
        self.soft = dags["soft"]
        self.prerequisites = build_prerequisite_graph(dags["hard"], dags["soft"])
        check_dag(self.prerequisites, "combined hard/soft")
        self._position = traversal.curriculum_positions(self.prerequisites, self.soft)

    # -----------------------------------------------------
    # Graph info
    # -----------------------------------------------------
    def roots(self):
        """Skills with no prerequisites: where the curriculum starts."""
        return sorted(n for n in self.prerequisites if self.prerequisites.in_degree(n) == 0)

    def topics(self):
        """Topic names in curriculum order (for the placement form)."""
        first = {}
        for n in self.order(self.prerequisites):
            first.setdefault(self.prerequisites.nodes[n]["topic"], n)
        return list(first)

    def skills_in_topic(self, topic):
        return sorted(n for n, d in self.prerequisites.nodes(data=True) if d["topic"] == topic)

    def node(self, skill_id):
        return self.prerequisites.nodes[skill_id]

    def order(self, skill_ids):
        """Sort skills prerequisites-first (curriculum order)."""
        return sorted(skill_ids, key=lambda s: self._position[s])

    def is_prerequisite(self, a, b):
        """True when `a` lies (transitively) behind `b`."""
        return a != b and a in nx.ancestors(self.prerequisites, b)

    # -----------------------------------------------------
    # Backward
    # -----------------------------------------------------
    def gap_walk(self, profile, start_skills, results=None):
        return gap_walk(self.prerequisites, profile, start_skills, results)

    def prerequisites_within(self, skill_ids, max_depth):
        return traversal.prerequisites_within(self.prerequisites, list(skill_ids), max_depth)

    # -----------------------------------------------------
    # Forward
    # -----------------------------------------------------
    def next_skills(self, profile):
        """Skills whose prerequisites are mastered; those also ready in the soft order come first."""
        mastered = profile.mastered
        unlocked = traversal.next_skills(self.prerequisites, mastered)
        return sorted(unlocked, key=lambda n: (not traversal.is_ready(self.soft, mastered, n), self._position[n]))

    def path_to(self, profile, target):
        """Ordered skills to learn to reach `target`."""
        mastered = profile.mastered
        todo = set(traversal.missing_prerequisites(self.prerequisites, mastered, target))
        if target not in mastered:
            todo.add(target)
        return self.order(todo)
