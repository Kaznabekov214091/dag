"""Data-quality checks on the soft/hard prerequisite graphs.

Each check returns issue dicts: check, severity, graph, skill_id, detail.
Errors block an import; warnings and info are reported only.
"""
import networkx as nx
import pandas as pd

from config import settings as cfg
from skill_dag.graph.builder import build_dag, build_prerequisite_graph

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def issue(check, severity, graph, skill_id, detail):
    return {"check": check, "severity": severity, "graph": graph, "skill_id": skill_id, "detail": detail}


def label(G, n):
    data = G.nodes[n]
    return f"{n} {data.get('topic')} / {data.get('skill')}"


# ---------------------------------------------------------
# Graph checks
# ---------------------------------------------------------
def find_cycles(G, name):
    try:
        cycle = nx.find_cycle(G)
    except nx.NetworkXNoCycle:
        return []
    path = " -> ".join(str(u) for u, _ in cycle) + f" -> {cycle[0][0]}"
    return [issue("cycle", "error", name, cycle[0][0], f"cycle: {path}")]


def unexpected_roots(G, name):
    """Skills with no prerequisites, other than the global starting skill."""
    start = min(G.nodes)
    return [
        issue("unexpected_root", "warning", name, n, f"{label(G, n)} has no prerequisites (empty cell?)")
        for n in sorted(G.nodes) if G.in_degree(n) == 0 and n != start
    ]


def dead_ends(G, name, skills_df):
    """Skills nothing depends on that are not the last skill of their topic."""
    last_in_topic = skills_df.groupby("topic")["id"].max().to_dict()
    return [
        issue("dead_end", "warning", name, n, f"{label(G, n)} is not a prerequisite of anything")
        for n in sorted(G.nodes)
        if G.out_degree(n) == 0 and n != last_in_topic[G.nodes[n]["topic"]]
    ]


def gate_groups(skills_df):
    """gate id -> ids of the non-gate skills of its topic since the previous gate."""
    groups = {}
    for _, topic_df in skills_df.sort_values("id").groupby("topic"):
        members = []
        for row in topic_df.itertuples(index=False):
            if row.sub_topic == cfg.GATE_SUB_TOPIC:
                groups[int(row.id)] = members
                members = []
            else:
                members.append(int(row.id))
    return groups


def gate_coverage(G, name, skills_df):
    """Every skill in a gate's group must be a (transitive) prerequisite of the gate."""
    issues = []
    for gate, members in gate_groups(skills_df).items():
        ancestors = nx.ancestors(G, gate)
        missing = [m for m in members if m not in ancestors]
        if missing:
            issues.append(issue("gate_coverage", "warning", name, gate, f"{label(G, gate)} does not require {missing}"))
    return issues


def redundant_edges(G, name):
    """Direct edges already implied by another path."""
    if not nx.is_directed_acyclic_graph(G):
        return []
    kept = set(nx.transitive_reduction(G).edges())
    return [
        issue("redundant_edge", "info", name, v, f"{u} -> {v} is implied by another path")
        for u, v in sorted(G.edges()) if (u, v) not in kept
    ]


# ---------------------------------------------------------
# Cross-graph / table checks
# ---------------------------------------------------------
def soft_hard_consistency(G_soft, G_hard):
    """A hard prerequisite must also come earlier in the soft order."""
    return [
        issue("soft_hard_order", "warning", "both", v, f"hard needs {u} before {v}, but soft does not")
        for u, v in sorted(G_hard.edges()) if u not in nx.ancestors(G_soft, v)
    ]


def duplicate_names(skills_df):
    issues = []
    for skill, group in skills_df.groupby("skill"):
        if group["topic"].nunique() > 1:
            ids = group["id"].tolist()
            issues.append(issue("duplicate_name", "info", "both", ids[0], f"'{skill}' is used by {ids}"))
    return issues


# ---------------------------------------------------------
# Run everything
# ---------------------------------------------------------
def run_all(skills_df, prereq_df, parse_problems=()):
    issues = [issue("parse", "error", "sheet", None, p) for p in parse_problems]
    if skills_df["id"].duplicated().any():
        dupes = sorted(skills_df.loc[skills_df["id"].duplicated(), "id"].unique().tolist())
        issues.append(issue("duplicate_id", "error", "sheet", dupes[0], f"duplicate skill ids {dupes}"))

    graphs = {t: build_dag(skills_df, prereq_df, t) for t in cfg.DAG_EDGE_TYPES}
    for name, G in graphs.items():
        issues += find_cycles(G, name)
        issues += unexpected_roots(G, name)
        issues += dead_ends(G, name, skills_df)
        if nx.is_directed_acyclic_graph(G):
            issues += gate_coverage(G, name, skills_df)
        issues += redundant_edges(G, name)
    issues += find_cycles(build_prerequisite_graph(graphs["hard"], graphs["soft"]), "combined")
    issues += soft_hard_consistency(graphs["soft"], graphs["hard"])
    issues += duplicate_names(skills_df)

    df = pd.DataFrame(issues, columns=["check", "severity", "graph", "skill_id", "detail"])
    if not df.empty:
        df = df.sort_values(["severity", "check", "graph", "skill_id"],
                            key=lambda s: s.map(SEVERITY_ORDER) if s.name == "severity" else s)
    return df.reset_index(drop=True)
