import networkx as nx


def build_dag(skills_df, prereq_df, edge_type):
    """Nodes are skills; an edge prerequisite -> skill for every row of `edge_type`."""
    G = nx.DiGraph()

    for _, row in skills_df.iterrows():
        G.add_node(
            int(row["id"]),
            topic=row["topic"],
            sub_topic=row["sub_topic"],
            skill=row["skill"],
        )

    edges = prereq_df[prereq_df["type"] == edge_type]
    for _, row in edges.iterrows():
        G.add_edge(int(row["prerequisite_id"]), int(row["skill_id"]))

    return G


def build_prerequisite_graph(hard, soft):
    """Each skill's hard prerequisites, or its soft ones when it has no hard ones."""
    G = nx.DiGraph()
    G.add_nodes_from(hard.nodes(data=True))
    for n in G:
        source = hard if hard.in_degree(n) else soft
        G.add_edges_from((p, n) for p in source.predecessors(n))
    return G


def check_dag(G, name):
    """Raise ValueError if the prerequisite graph contains a cycle."""
    if not nx.is_directed_acyclic_graph(G):
        raise ValueError(f"{name} prerequisites contain a cycle: {nx.find_cycle(G)}")
