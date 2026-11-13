"""Pure graph walks. Edges point prerequisite -> skill; `mastered` is a set of skill ids."""
from collections import deque

import networkx as nx


def missing_prerequisites(G, mastered, skill_id):
    """Unmastered (transitive) prerequisites of `skill_id`, closest first.

    The walk stops at mastered skills: whatever lies behind a mastered skill is assumed known.
    """
    seen = {skill_id}
    queue = deque([skill_id])
    missing = []
    while queue:
        node = queue.popleft()
        for prereq in sorted(G.predecessors(node)):
            if prereq in seen or prereq in mastered:
                continue
            seen.add(prereq)
            missing.append(prereq)
            queue.append(prereq)
    return missing


def prerequisites_within(G, skill_ids, max_depth):
    """{prerequisite: depth} up to `max_depth` steps back from `skill_ids` (the skills themselves excluded)."""
    depth = {s: 0 for s in skill_ids}
    queue = deque(skill_ids)
    while queue:
        node = queue.popleft()
        if depth[node] >= max_depth:
            continue
        for prereq in sorted(G.predecessors(node)):
            if prereq not in depth:
                depth[prereq] = depth[node] + 1
                queue.append(prereq)
    return {s: d for s, d in depth.items() if d > 0}


def is_ready(G, mastered, skill_id):
    return all(p in mastered for p in G.predecessors(skill_id))


def next_skills(G, mastered):
    """Unmastered skills whose prerequisites are all mastered (the learning frontier)."""
    return sorted(n for n in G if n not in mastered and is_ready(G, mastered, n))


def curriculum_positions(G, order_graph=None):
    """{skill: position} in a topological order of `G`, following `order_graph` too when it agrees."""
    combined = G if order_graph is None else nx.compose(G, order_graph)
    if not nx.is_directed_acyclic_graph(combined):
        combined = G
    return {n: i for i, n in enumerate(nx.lexicographical_topological_sort(combined))}
