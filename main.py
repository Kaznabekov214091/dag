from skill_dag.pipeline import load_dags

if __name__ == "__main__":
    for edge_type, G in load_dags().items():
        print(f"{edge_type}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
