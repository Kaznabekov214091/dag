# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Backend engine for adaptive K-12 math practice on **paper worksheets**. Skills form a DAG; each student has a mastery profile; teachers create assignments (when, for whom, optional settings) and the engine decides what questions each student's worksheet gets. Worksheets are printed, scanned and graded elsewhere; graded scores come back through the API and update mastery.

Full docs: `docs/README.md` (concepts and flows) and `docs/reference.md` (every file and function).

## Working rule (from the user, applies to everything)

**Build only what the user told you or agreed to. Do not add your own logic, rules, features or defaults.**
- Giving your opinion is welcome: point out problems, risks and better options, and disagree when you think the user is wrong. But that is advice only. Nothing goes into code or docs until the user agrees to it.
- When something needed isn't specified (e.g. how to pick questions), stop and ask; don't fill the gap with your own choice.
- Existing logic the user never specified (e.g. question picking in `questions/`: difficulty from mastery, unseen first) is a placeholder until the user gives the rules.

## Commands

Run everything from the project root (packages are imported as top-level: `config`, `db`, `skill_dag`, ...). Python venv is `.venv`.

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload                                   # API, docs at http://localhost:8000/docs
python scripts/import_skills.py --file algebra.xlsx --dry-run   # check sheet + show DB diff
python scripts/import_skills.py --file algebra.xlsx             # import (exit 1 on sheet errors)
pytest -q tests                                                 # logic tests, no DB needed
TEST_DB_URL=postgresql+psycopg2://postgres:root@localhost:5432/dag_test pytest -q tests   # + API/DB flow
pytest -q tests/test_placement.py -k window                     # single test
python debug/draw_dags.py                                       # PNG/HTML of the DAGs (debug only, needs debug/requirements.txt)
```

`tests/test_api_flow.py` **drops and recreates every table** in the `TEST_DB_URL` database — never point it at real data. `DB_URL` (env) selects the database for everything else; `config/settings.py` holds every tunable (level rules, thresholds, placement limits, worksheet mix).

## Architecture

- **Schema**: `db/schema.sql` (plain SQL, applied with `psql -f`) is the blueprint: `skills` / `skill_prerequisites` are copied from the actual DB, every other table comes from the user's schema design (only change: `node_id` → `skills(id)`). The skill graph lives in `skills` / `skill_prerequisites` (`type` = `soft`|`hard`), filled only by `scripts/import_skills.py` from the spreadsheet (the spreadsheet is the editing tool; the DB is the source of truth). All `node_id` columns reference `skills(id)`. Don't add DB columns without the user's say — missing DB features are handled in Python (e.g. "placed" is derived from flags).
- **Two graphs → one prerequisite graph**: `SkillNavigator` (`skill_dag/navigator.py`) combines them: a skill's hard prerequisites, or its soft ones when it has none. That combined graph drives gap detection (backward) and unlocking (forward); the soft graph only ranks/orders. Edges point prerequisite → skill. Loaded once at API startup (`app.state.navigator`); `POST /admin/reload-graph` after an import.
- **Gap walk** (`skill_dag/gap_walk.py`) is stateless: backward from start skills, each skill settled by `results` (assessments) or the profile (weak → failed, learning/mastered → passed), unknown → `pending`. Replaying the same results gives the same walk — this is how paper placement works without storing session state.
- **Mastery** (`mastery/`, user's design, no BKT): each skill has a level `student_mastery.difficulty` (1 easy / 2 medium / 3 hard). Smoothed rate `(correct+1)/(answers+2)` over the last 20 answers per level (history from `worksheet_items` + `questions.difficulty`). 10+ answers at rate ≥ 80% → next level; level 3 passed → mastered (`mastered_at` set). Levels go down only in placement (medium asked; fail → level 1). Sheets mix the current level with the one below only (30/70). `mastery` = average of level rates (profile number; weak < `WEAK_BELOW`). Mastery is never edited by hand (teachers can't). `flags`: `placement` (= placed), `inferred`, `gap`, `window` (practice window), `stuck` (rate < 50% after 5 answers → backward gap detection), `review_failed`. Reviews follow `REVIEW_INTERVALS_DAYS`; a mastered skill stays mastered.
- **Placement** (`placement/`): puts a new student at the right starting point; no extra tables. Questionnaire per topic (dont_know/partly/well): nothing known → beginner, no test, rows for the roots (`beginner_states`). Otherwise a window: end = Gates of partly/well topics, start = Gates of well topics, window = end + `PLACEMENT_WINDOW_DEPTH` levels, not behind start. While a student isn't placed, every graded worksheet is a placement round; a skill counts as passed/failed only when its smoothed rate over all rounds is clear (≥ 0.75 / ≤ 0.35), else it's asked again; the gap walk runs down from end and may go below the window (lower bound moves). End skills are recovered as the outermost skills of round 1. Look-ahead fills the sheet, inside the window. `finish` writes mastery with flags.
- **Worksheets** (`worksheets/`): `selector.plan_worksheet` decides skills+counts (placement round, or practice: a saved window of 3 ready nodes (`window` flag, stays until mastered; free place → same topic as the node that left, else gaps then lowest id), 15 questions split equally; teachers can't change what's on a sheet), `blueprint` turns the plan + profile into slots (node, difficulty) per question, `questions.picker` fills each slot from the pool (unseen first), `builder` ties them together, `service` generates per student and evaluates graded sheets (placement step or level/rate update).
- **API** (`api/`): thin FastAPI layer; the frontend (JS, separate developer) works from `/docs`.
- `debug/` is not part of the app.
