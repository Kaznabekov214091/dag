"""Debug only: draw the soft/hard DAGs to PNG + HTML for inspection.

Usage (from the project root): python debug/draw_dags.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skill_dag.pipeline import load_dags
from visualize import draw_interactive, draw_static

OUTPUT_DIR = ROOT / "output"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    for edge_type, G in load_dags().items():
        if G.number_of_edges() == 0:
            print(f"Skipping {edge_type}: no edges")
            continue
        title = f"{edge_type.capitalize()} Prerequisites"
        draw_static(G, OUTPUT_DIR / f"{edge_type}_dag.png", title)
        draw_interactive(G, OUTPUT_DIR / f"{edge_type}_dag.html")


if __name__ == "__main__":
    main()
