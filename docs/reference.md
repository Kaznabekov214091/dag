# Code reference — every file and function

Read [README.md](README.md) first for the concepts. Here, "profile" means a `StudentProfile` and "navigator" a `SkillNavigator`. Skill ids are the `skills.id` values (e.g. `302`).

```
config/      settings for everything
db/          connection + schema blueprint
skill_dag/   the skill graph and moving on it (forward / backward)
mastery/     student profile, levels + smoothed rate, reviews
questions/   picking questions from the pool
placement/   placement form and rounds
worksheets/  deciding and building worksheets, evaluating them
importer/    spreadsheet → DB (with checks)
scripts/     command-line entry points
api/         FastAPI app for the frontend
tests/       pytest
debug/       drawing the DAGs (not part of the app)
main.py      prints a summary of the graphs in the DB
```

---

## `config/settings.py`
Every setting, in one place. Values can be read from environment variables where noted.

| Setting | Meaning |
|---|---|
| `DB_URL` | database URL (env `DB_URL`) |
| `CORS_ORIGINS` | frontend addresses allowed to call the API (env `CORS_ORIGINS`, comma separated) |
| `DAG_EDGE_TYPES` | `("soft", "hard")`, the prerequisite types |
| `GATE_SUB_TOPIC` | `"Gate"`, the sub-topic marking a topic checkpoint |
| `LEVELS` | `(1, 2, 3)`: easy, medium, hard (`student_mastery.difficulty`) |
| `RATE_WINDOW` | the rate counts the last 20 answers at a level |
| `LEVEL_UP_MIN_ANSWERS`, `LEVEL_UP_RATE` | 10 answers and rate ≥ 0.8 → next level; at level 3 → mastered |
| `PREVIOUS_LEVEL_SHARE` | 0.3 of a skill's questions from the level below (level 2+) |
| `STUCK_MIN_ANSWERS`, `STUCK_BELOW` | 5 answers and rate < 0.5 at the current level → `stuck` |
| `WEAK_BELOW` | mastery number below this is weak, i.e. a gap (0.5) |
| `PASS_SCORE` | average score on a skill in one worksheet that counts as passing a review (0.7) |
| `PLACEMENT_PASS_RATE`, `PLACEMENT_FAIL_RATE` | placement confidence: smoothed rate ≥ 0.75 clearly passed, ≤ 0.35 clearly failed, in between asked again |
| `REVIEW_INTERVALS_DAYS` | days until the next review, by `review_level` |
| `FLAG_*` | flag names stored in `student_mastery.flags` |
| `PLACEMENT_DIFFICULTY` | placement questions are medium (2) |
| `PLACEMENT_NUM_QUESTIONS` | questions per placement sheet (10) |
| `PLACEMENT_MAX_ROUNDS`, `PLACEMENT_QUESTIONS_PER_SKILL`, `PLACEMENT_MAX_SKILLS_PER_ROUND`, `PLACEMENT_WINDOW_DEPTH` | placement limits; the window is end + this many prerequisite levels |
| `WINDOW_SIZE` | nodes in the practice window (3) |
| `PRACTICE_NUM_QUESTIONS` | questions per practice sheet, split equally over the window (15) |

## `db/`
### `connection.py`
- **`get_engine(url=DB_URL)`**: returns the shared SQLAlchemy engine (one connection pool per URL, cached). Use it everywhere instead of `create_engine`.

### `schema.sql`
The table creation script, in plain SQL. Apply it once with `psql -U postgres -d dag -f db/schema.sql`.
- **`skills`, `skill_prerequisites`:** copied from the actual database, where they already exist (`IF NOT EXISTS`, so they're left alone).
- **Everything else** (organizations, users, classes, class_students, questions, student_mastery, assignments, worksheets, worksheet_items, answer_boxes): from the schema design. The only change is that `node_id` references `skills(id)`. These are plain `CREATE TABLE` statements, so running the file a second time fails on them.

---

## `skill_dag/`: the skill graph

### `db/repository.py`
- **`fetch_skills(engine)`**: DataFrame `id, topic, sub_topic, skill`.
- **`fetch_prerequisites(engine)`**: DataFrame `skill_id, prerequisite_id, type`.

### `pipeline.py`
- **`load_dags(engine=None)`**: reads both tables and returns `{"soft": DiGraph, "hard": DiGraph}`. Raises `ValueError` if either graph has a cycle.

### `graph/builder.py`
- **`build_dag(skills_df, prereq_df, edge_type)`**: a `networkx.DiGraph` with every skill as a node (attributes `topic`, `sub_topic`, `skill`) and an edge **prerequisite → skill** for each row of that type.
- **`build_prerequisite_graph(hard, soft)`**: the combined graph. Each skill takes its hard prerequisites, or its soft ones if it has none.
- **`check_dag(G, name)`**: raises `ValueError` naming the cycle if `G` isn't acyclic.

### `graph/traversal.py`
Pure graph functions; `mastered` is a set of skill ids.
- **`missing_prerequisites(G, mastered, skill_id)`**: unmastered prerequisites behind a skill, closest first. Stops at mastered skills.
- **`prerequisites_within(G, skill_ids, max_depth)`**: `{prerequisite: depth}` up to `max_depth` steps back from the given skills (the skills themselves excluded).
- **`is_ready(G, mastered, skill_id)`**: True when all its prerequisites are mastered.
- **`next_skills(G, mastered)`**: unmastered skills that are ready (the frontier).
- **`curriculum_positions(G, order_graph=None)`**: `{skill: position}` in a topological order, following the soft order too when it doesn't conflict.

### `gap_walk.py`
- **`GapWalk`** (result): `passed`, `failed`, `pending` (unknown skills to test next) and `gaps` (failed skills whose prerequisites all passed). `done` is True when nothing is pending.
- **`gap_walk(G, profile, start_skills, results=None)`**: the backward walk from `start_skills`. Each skill is settled by `results` (`{skill: passed}`) or else by the profile (weak = failed; learning or mastered = passed). Unknown skills become `pending`. A failed skill opens its prerequisites; a passed one stops there. Stateless, so replaying the same results always gives the same walk.

### `navigator.py`: `SkillNavigator(dags)`
Built once from `load_dags()`. Holds `soft` and the combined `prerequisites` graph, and checks the combined graph for cycles.

| Method | Returns |
|---|---|
| `roots()` | skills with no prerequisites (where the curriculum starts) |
| `topics()` | topic names in curriculum order |
| `skills_in_topic(topic)` | skill ids of a topic |
| `node(skill_id)` | the skill's attributes (`topic`, `sub_topic`, `skill`) |
| `order(skill_ids)` | the skills sorted prerequisites first |
| `is_prerequisite(a, b)` | True if `a` lies (transitively) behind `b` |
| `gap_walk(profile, start_skills, results=None)` | backward walk (see above) on the combined graph |
| `prerequisites_within(skill_ids, max_depth)` | prerequisites up to a depth |
| `next_skills(profile)` | unlocked skills; ones also ready in the soft order come first |
| `path_to(profile, target)` | ordered skills still to learn to reach `target` |

---

## `mastery/`: the student profile

### `profile.py`
- Status constants: **`MASTERED`, `LEARNING`, `WEAK`, `UNKNOWN`**.
- **`SkillState`**: one `student_mastery` row: `mastery`, `mastered_at`, `next_review_at`, `review_level`, `flags`.
  - `is_mastered`: mastery ≥ threshold.
  - `is_due(now)`: a review is due.
- **`StudentProfile(student_id, skills)`**: `skills` is `{skill_id: SkillState}`.

| Member | Returns |
|---|---|
| `mastered` | set of mastered skill ids |
| `placed` | True once any row has the `placement` flag |
| `mastery(skill_id)` | mastery value, or `None` with no row |
| `level(skill_id)` | current difficulty level, 1 with no row |
| `status(skill_id)` | one of the four statuses |
| `flagged(flag)` | skills carrying a flag |
| `due_reviews(now)` | mastered skills due for review, oldest first |
| `with_states(updates)` | a new profile with some rows replaced |

### `rate.py`
`history` = one skill's graded answers, oldest first: `[(question difficulty, score), ...]`.
- **`recent(history, level)`**: scores of the last `RATE_WINDOW` answers at a level.
- **`rate(scores)`**: `(sum + 1) / (count + 2)`.
- **`passed_level(history, level)`**: at least `LEVEL_UP_MIN_ANSWERS` and rate ≥ `LEVEL_UP_RATE`.
- **`next_level(history, level)`**: moves up while the current level is passed; never down.
- **`is_stuck(history, level)`**: at least `STUCK_MIN_ANSWERS` and rate < `STUCK_BELOW`.
- **`overall(history)`**: the profile number, the average of the level rates.
- **`level_mix(level, count)`**: `{difficulty: count}` for one skill on a sheet: the current level plus `PREVIOUS_LEVEL_SHARE` from the level below.

### `reviews.py`
- **`next_review(review_level, now)`**: when to review next: `now + REVIEW_INTERVALS_DAYS[level]` (the last interval repeats).

### `apply.py`
- **`scores_by_skill(items)`**: `[(skill, score), ...]` → `{skill: [scores]}`.
- **`apply_practice(profile, items, histories, now)`**: mastery updates for a graded practice sheet, `{skill: SkillState}`. `histories` holds every graded answer per skill, this sheet included.
- **`update_skill(old, history, sheet_scores, now)`**: one skill's update:
  - not mastered: level up by `next_level`; level 3 passed → mastered (`mastered_at`, first review, `gap`/`stuck` cleared); otherwise `mastery = overall(history)` and `stuck` set or cleared;
  - mastered: only a due review counts; a pass (`PASS_SCORE` on this sheet) moves `review_level` up, a fail resets it and adds `review_failed`. The skill stays mastered.

### `repository.py`
- **`fetch_profile(conn, student_id)`**: loads the `StudentProfile`. A student with no rows gets an empty (new) profile.
- **`save_states(conn, student_id, updates)`**: inserts or updates `student_mastery` rows inside the caller's transaction.

---

## `questions/`: the question pool

### `repository.py`
- **`fetch_question_ids(conn, node_id, difficulty, limit, exclude_ids=())`**: random question ids for a skill, closest to the difficulty first, skipping excluded ids.
- **`seen_question_ids(conn, student_id)`**: every question already put on any of the student's worksheets.

### `picker.py`
- **`pick_for_blueprint(conn, student_id, slots)`**: one question per blueprint slot (node, difficulty), using `pick_questions`. Returns `[(slot, question_id)]` in slot order; slots the pool can't fill are left out.
- **`pick_questions(conn, node_id, count, difficulty, seen, picked)`**: unseen questions first. If the pool runs out it repeats older ones, but never one already on this sheet (`picked`).

---

## `placement/`

### `form.py`
- **`PlacementForm(answers)`**: the questionnaire, `{topic: "dont_know" | "partly" | "well"}`. Missing topics = `dont_know`.
- **`Window(end, skills)`**: what placement tests. `beginner` is true when there is no end.
- **`placement_window(navigator, form)`**: answers → window.
  - nothing known → beginner;
  - end = `checkpoint` of the `partly`/`well` topics, keeping the `outermost` ones;
  - start = `checkpoint` of the `well` topics;
  - skills = `window_skills(navigator, end, start)`.
  - Raises `ValueError` for an unknown topic or answer.
- **`window_skills(navigator, end, start=())`**: end + prerequisites up to `PLACEMENT_WINDOW_DEPTH` levels below, dropping anything behind a start skill.
- **`checkpoint(navigator, topic)`**: the topic's Gate, or its last skill.
- **`outermost(navigator, skills)`**: drops skills lying behind another one in the set.

### `rounds.py`
- **`PlacementState`**: `window`, `walk`, `rounds_done`, `scores` (all scores so far).
  - `finished`: at least one round done, and either nothing pending or the round limit reached.
- **`placement_state(navigator, profile, graded_rounds, form=None)`**: rebuilds placement from the student's graded worksheets (oldest first). With no rounds yet, the window comes from the questionnaire; later, its end skills are the outermost skills of round 1, and the window is rebuilt from them (depth only, as start isn't stored).
- **`placement_verdict(scores)`**: `True` clearly passed, `False` clearly failed, `None` not sure yet (asked again). Scores add up over all rounds.
- **`beginner_states(navigator)`**: the rows for a beginner: one per root, flag `placement` (so the student is placed), no test.
- **`next_round(navigator, profile, state, num_questions)`**: `{skill: question count}` for the next sheet. Pending skills come first (round 1: every end skill), then `look_ahead` fills the rest with untested skills behind them.
- **`look_ahead(navigator, skills, window, depth)`**: skills behind `skills`, closest first; inside the window for skills in it, free below it once the walk has left the window.
- **`finish(navigator, profile, state, now)`**: the mastery rows that close placement:
  - passed → mastered at level 3 (`placement`), first review scheduled;
  - failed → level 1, mastery from its scores (`placement`, plus `gap` for the deepest ones);
  - untested skills behind passed ones → mastered (`inferred`), with no reviews.

---

## `worksheets/`

### `selector.py`: decides WHAT
- **`WorksheetPlan`**: `kind` (`"placement"` / `"practice"`), `skill_counts` (`{skill: n}`) and `difficulty` (`None` = from mastery).
- **`plan_worksheet(navigator, profile, graded_rounds=(), form=None)`**:
  1. not placed → the next placement round, `PLACEMENT_NUM_QUESTIONS` (a beginner must already have `beginner_states`);
  2. otherwise → practice: `update_window`, `PRACTICE_NUM_QUESTIONS` split equally.
- **`update_window(navigator, profile, size=WINDOW_SIZE)`**: `(window, {skill: SkillState})`. Keeps the `window`-flagged nodes that aren't mastered; drops the flag from mastered ones; fills free places with the next ready node in the same topic as a node that left, then ready gaps, then other ready nodes, lowest id first. The updates (flags) are saved by `service.generate`.
- **`WorksheetPlan.state_updates`**: the window flag changes to save.
- **`split_equally(nodes, num_questions)`**: `{node: count}`, equal shares; any remainder goes to the first nodes.

### `blueprint.py`
- **`Slot(node_id, difficulty)`**: one question still to pick.
- **`blueprint(navigator, profile, plan)`**: the list of slots for the sheet, prerequisites first. Each node's slots are split over difficulties by its level in the profile (`level_mix`), or all at the plan's fixed difficulty (placement).

### `builder.py`
- **`WorksheetItem(position, question_id, node_id, difficulty)`**: one numbered question.
- **`build_items(conn, navigator, profile, plan)`**: plan → `blueprint` → `pick_for_blueprint` → numbered questions. Returns `(items, short)`; `short` lists skills that got fewer questions than planned because the pool was too small.

### `repository.py`
- **`fetch_assignment(conn, id)`** / **`create_assignment(conn, class_id, teacher_id, title, due_at)`** (`assignments.num_questions` is no longer used).
- **`class_student_ids(conn, class_id)`**: the students in a class.
- **`create_worksheet(conn, assignment_id, student_id, items)`**: inserts the worksheet and its items, and returns the id.
- **`fetch_worksheet(conn, id)`**: the header plus items, each with its question's skill and difficulty, score and feedback.
- **`save_scores(conn, id, {position: score})`**: stores scores and marks the sheet `submitted`.
- **`mark_evaluated(conn, id)`**.
- **`graded_rounds(conn, student_id)`**: every evaluated worksheet of the student, oldest first, as `[(skill, score), ...]`.
- **`answer_history(conn, student_id, node_ids)`**: `{skill: [(difficulty, score), ...]}`, every graded answer on those skills, oldest first.

### `service.py`: `WorksheetService(engine, navigator)`
- **`generate(assignment_id, student_ids=None, forms=None)`**: one worksheet per student (default: the whole class), in one transaction. Returns `GeneratedWorksheet` objects (`student_id`, `worksheet_id`, `kind`, `num_questions`, `short_skills`).
- **`evaluate(worksheet_id, now=None)`**: the scores must already be stored.
  - **placement:** replays the rounds and, if finished, writes the placement results;
  - **practice:** loads the answer history and updates levels and rates.
  - Refuses sheets that are already evaluated or have unscored items.
  - Returns an `Evaluation` (`kind`, `placement_finished`, `gaps`, `updated_skills`).

---

## `importer/`: spreadsheet → DB

### `excel_reader.py`
- **`read_sheet(path, sheet=0)`**: raw rows, with headers trimmed and ids as integers.
- **`to_skills_table(df)`**: rows for `skills`; empty cells become `None` (NULL in the DB).
- **`parse_cell(cell)`**: every integer in a prerequisite cell (`101`, `"101, 103"`, `"(105),(205)"`).
- **`to_prerequisite_rows(df)`**: rows for `skill_prerequisites`, plus a list of problems (self-references, unknown ids).

### `checks.py`
- **`run_all(skills_df, prereq_df, parse_problems=())`**: a DataFrame of issues (`check`, `severity`, `graph`, `skill_id`, `detail`). **Errors** block an import.
  - errors: parse problems, duplicate ids, cycles in soft, hard or the combined graph;
  - warnings: unexpected roots, dead ends, Gate coverage, hard edges that conflict with the soft order;
  - info: redundant edges, duplicate names.
- Individual checks: `find_cycles`, `unexpected_roots`, `dead_ends`, `gate_groups`, `gate_coverage`, `redundant_edges`, `soft_hard_consistency`, `duplicate_names`.

### `sync.py`
- **`SyncPlan`**: `added`, `changed`, `removed` (unused, so deleted), `kept_removed` (gone from the sheet but used by questions or mastery, so **kept**), `edges_added`, `edges_removed`.
- **`used_skill_ids(conn)`**: skills referenced by `questions` or `student_mastery`.
- **`plan_sync(conn, skills_df, prereq_df)`**: compares the sheet with the DB.
- **`apply_sync(conn, plan, skills_df, prereq_df)`**: inserts or updates skills, replaces the edges, and deletes only unused removed skills. Run it inside one transaction.

## `scripts/import_skills.py`
`python scripts/import_skills.py --file algebra.xlsx [--dry-run]`: runs the checks (exit 1 on errors), prints the changes, then imports (or not, with `--dry-run`). After a real import, call `POST /admin/reload-graph`.

---

## `api/`: FastAPI
- **`main.py`**: the `app`. On startup it loads the graph into `app.state.navigator`; it also adds CORS and the routers. Run with `uvicorn api.main:app --reload`.
- **`deps.py`**: request dependencies: `engine()`, `navigator(request)`, `worksheet_service(request)`.
- **`schemas.py`**: Pydantic request and response models (the contract shown at `/docs`).
- **`routes/skills.py`**: `GET /skills`, `GET /skills/topics`, `POST /admin/reload-graph`.
- **`routes/students.py`**:
  - `GET /students/{id}/profile`
  - `GET /students/{id}/next-skills`
  - `GET /students/{id}/path/{target}`
  - `GET /students/{id}/gaps/{skill}`: returns `gaps`, `to_assess` and `weak_path`
  - helper `load_profile(engine, id)`
- **`routes/worksheets.py`**:
  - `POST /assignments`
  - `POST /assignments/{id}/worksheets`
  - `GET /worksheets/{id}`
  - `POST /worksheets/{id}/scores`: needs a score for every position, then evaluates the sheet

Errors: `404` not found, `422` bad input, `409` already evaluated.

---

## `tests/`
- **`conftest.py`**: `small_nav` (an 8-skill hand-made graph) and `algebra_nav` (the real spreadsheet). Sets `DB_URL` from `TEST_DB_URL`.
- **`test_mastery.py`**: smoothed rate, level up (never down), level mix, mastered at level 3, stuck, reviews.
- **`test_graph.py`**: the soft fallback, the gap walk, forward moves, depth limits, import cycle check.
- **`test_placement.py`**: simulated students through paper rounds (beginner without a test, window and start, lower bound moving below the window, round limit, the real curriculum).
- **`test_selector.py`**: window (gaps first, not-ready skipped, stays until mastered, same-topic stream, lowest topic number), equal split, placement plan, blueprint.
- **`test_api_flow.py`**: end to end on a throwaway DB (only with `TEST_DB_URL`). It **drops all tables** there.

## `debug/` (not part of the app)
- **`visualize.py`**: `draw_static` (PNG), `node_levels`, `draw_interactive` (HTML).
- **`draw_dags.py`**: `python debug/draw_dags.py` writes `output/{soft,hard}_dag.{png,html}`. Needs `debug/requirements.txt`.

## `main.py`
Prints the node and edge counts of the graphs loaded from the DB, as a quick check that the DB and the graph are fine.
