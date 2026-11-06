import numbers
import re

import pandas as pd

# spreadsheet column -> meaning
COL_ID = "ID"
COL_TOPIC = "Topic"
COL_SUB_TOPIC = "Sub Topic"
COL_SKILL = "Skill"
EDGE_COLUMNS = {"soft": "Soft", "hard": "Hard"}


def read_sheet(path, sheet=0):
    """Raw rows with clean headers and int IDs."""
    df = pd.read_excel(path, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(subset=[COL_ID, COL_SKILL]).reset_index(drop=True)
    df[COL_ID] = df[COL_ID].astype(int)
    return df


def to_skills_table(df):
    """Rows for `skills`."""
    clean = lambda v: None if pd.isna(v) else str(v).strip()
    out = pd.DataFrame({"id": df[COL_ID].astype(int)})
    # object columns holding real None (not NaN), so empty cells reach the DB as NULL
    for name, col in (("topic", COL_TOPIC), ("sub_topic", COL_SUB_TOPIC), ("skill", COL_SKILL)):
        out[name] = pd.Series([clean(v) for v in df[col]], index=df.index, dtype=object)
    return out


def parse_cell(cell):
    """Handles 101, 101.0, '(105),(205)', '101, 103', '101; 103'."""
    if pd.isna(cell):
        return []
    if isinstance(cell, numbers.Number):
        return [int(cell)]
    return [int(n) for n in re.findall(r"\d+", str(cell))]


def to_prerequisite_rows(df):
    """Rows for `skill_prerequisites`, plus problems found while parsing (self-loops, unknown ids)."""
    known = set(df[COL_ID])
    rows, seen, problems = [], set(), []

    for edge_type, col in EDGE_COLUMNS.items():
        for _, row in df.iterrows():
            skill_id = int(row[COL_ID])
            for prereq_id in parse_cell(row[col]):
                key = (skill_id, prereq_id, edge_type)
                if key in seen:
                    continue
                seen.add(key)
                if prereq_id == skill_id:
                    problems.append(f"{edge_type}: {skill_id} lists itself as a prerequisite")
                elif prereq_id not in known:
                    problems.append(f"{edge_type}: {skill_id} needs unknown skill {prereq_id}")
                else:
                    rows.append(key)

    return pd.DataFrame(rows, columns=["skill_id", "prerequisite_id", "type"]), problems
