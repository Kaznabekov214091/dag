import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network


# ---------------------------------------------------------
# Static image via pygraphviz (hierarchical layout)
# ---------------------------------------------------------
def draw_static(G, filename, title):
    pos = nx.nx_agraph.graphviz_layout(G, prog="dot")
    labels = {n: G.nodes[n]["skill"] for n in G.nodes}

    plt.figure(figsize=(30, 20))
    nx.draw(
        G, pos,
        labels=labels,
        node_size=800,
        node_color="lightblue",
        font_size=6,
        arrows=True,
        arrowsize=10,
    )
    plt.title(title)
    plt.savefig(filename, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {filename}")


# ---------------------------------------------------------
# Interactive HTML via pyvis (recommended for inspection)
# ---------------------------------------------------------
def node_levels(G):
    """Level = longest path from any root (so Addition = 0, Subtraction = 1, etc.)."""
    levels = {}
    for generation in nx.topological_generations(G):
        for node in generation:
            preds = list(G.predecessors(node))
            if preds:
                levels[node] = max(levels[p] for p in preds) + 1
            else:
                levels[node] = 0
    return levels


def draw_interactive(G, filename):
    net = Network(height="900px", width="100%", directed=True, notebook=False)
    levels = node_levels(G)

    for node, data in G.nodes(data=True):
        label = data.get("skill", str(node))
        title = f"{data.get('topic')} / {data.get('sub_topic')}"
        net.add_node(node, label=label, title=title, level=levels[node])

    for source, target in G.edges():
        net.add_edge(source, target)

    net.set_options("""
    {
      "layout": {
        "hierarchical": {
          "enabled": true,
          "direction": "UD",
          "sortMethod": "directed",
          "levelSeparation": 150,
          "nodeSpacing": 200,
          "treeSpacing": 250
        }
      },
      "physics": { "enabled": false },
      "edges": {
        "smooth": {
          "type": "cubicBezier",
          "forceDirection": "vertical",
          "roundness": 0.4
        }
      }
    }
    """)
    net.write_html(str(filename))
    print(f"Saved {filename}")
