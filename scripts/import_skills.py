"""Import the skill graph from the spreadsheet into the DB (checks first, nothing student-facing is dropped).

Usage: python scripts/import_skills.py --file algebra.xlsx [--dry-run]
Exit code 1 when the sheet has errors (nothing is written).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.connection import get_engine
from importer.checks import run_all
from importer.excel_reader import read_sheet, to_prerequisite_rows, to_skills_table
from importer.sync import apply_sync, plan_sync


def print_issues(issues):
    for (severity, check), group in issues.groupby(["severity", "check"], sort=False):
        print(f"[{severity.upper()}] {check} ({len(group)})")
        for row in group.itertuples(index=False):
            print(f"  {row.graph:<8} {row.detail}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="spreadsheet to import")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args()

    raw = read_sheet(args.file)
    skills = to_skills_table(raw)
    prereqs, problems = to_prerequisite_rows(raw)
    issues = run_all(skills, prereqs, problems)
    print_issues(issues)

    errors = int((issues["severity"] == "error").sum())
    if errors:
        print(f"\n{errors} error(s): nothing imported")
        return 1

    with get_engine().begin() as conn:
        plan = plan_sync(conn, skills, prereqs)
        print(f"\nskills: +{len(plan.added)} added, ~{len(plan.changed)} changed, -{len(plan.removed)} removed")
        print(f"edges:  +{plan.edges_added} added, -{plan.edges_removed} removed")
        if plan.kept_removed:
            print(f"WARNING: kept {plan.kept_removed}: gone from the sheet but used by questions or mastery")

        if args.dry_run or not plan.has_changes:
            print("dry run: nothing written" if args.dry_run else "already up to date")
            return 0
        apply_sync(conn, plan, skills, prereqs)
    print("imported")
    return 0


if __name__ == "__main__":
    sys.exit(main())
