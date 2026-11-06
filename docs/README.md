# Adaptive math practice — how it works

This is the backend engine. It decides **what each student practises**, on paper worksheets, from a graph of math skills and each student's mastery profile. The frontend (JavaScript) talks to it over HTTP through the API.

Every file and function is described in [reference.md](reference.md).

---

## 1. The big picture

```
 Teacher (frontend)                       Engine (this project)                     Postgres
 ──────────────────                       ─────────────────────                     ────────
 creates an assignment  ───────────────►  for each chosen student:
 (when, for whom,                           read profile ──────────────────────────► student_mastery
  optional settings)                        not placed?  → placement round
                                            placed?      → practice (gaps/next/reviews
                                                           or the teacher's targets)
                                            pick questions ─────────────────────────► questions
                                            save worksheet ─────────────────────────► worksheets, worksheet_items
 prints, students solve,
 scans, grades
 sends scores  ────────────────────────►  evaluate:
                                            placement → next round or finish placement
                                            practice  → level + rate update ────────► student_mastery
```

**The teacher decides WHEN and for WHOM. The engine decides WHAT.**

---

## 2. Core ideas

### Skill graph (DAG)
- Every skill (`skills` table) has an id (e.g. `302`), a topic, an optional sub-topic and a name. A sub-topic of `Gate` marks a topic's mastery checkpoint.
- Prerequisites (`skill_prerequisites`) come in two kinds:
  - **hard**: real dependencies ("you can't do B without A");
  - **soft**: the recommended curriculum order.
- The engine combines them into one **prerequisite graph**: each skill uses its hard prerequisites, or its soft ones if it has no hard ones. Every decision about gaps and unlocking uses this graph. The soft order is only used for ranking and ordering.
- The spreadsheet (`algebra.xlsx`) is where the curriculum is edited. `scripts/import_skills.py` checks it and loads it into the DB. The engine only reads the DB.

### Moving on the graph
- **Backward (gap detection):** start from a skill the student fails and walk back through its prerequisites until you reach skills they know. The **gaps** are the deepest failing skills, the ones whose own prerequisites are all fine. Fix those first.
- **Forward (learning):** a skill is **unlocked** when all its prerequisites are mastered. `next_skills` lists the unlocked skills, and `path_to` gives the ordered list of skills to learn to reach a target.

### Mastery (difficulty levels + smoothed rate)
- Each skill has a **level** (`student_mastery.difficulty`): 1 easy, 2 medium, 3 hard. A student starts at 1.
- **Rate** at a level = `(correct + 1) / (answers + 2)` over the last 20 answers at that level. With no answers it's 50%; one lucky answer gives only 67%.
- **Level up:** at least 10 answers at the current level and a rate ≥ 80%. In practice the level never goes down (only placement can start a skill lower).
- **Mixing:** at level 2 and 3, about 30% of a skill's questions come from the level just below (level 3 mixes with 2 only), the rest from the current level.
- **Mastered:** level 3 passed by the same rule (10+ answers, rate ≥ 80%), so easy and medium are done and hard is at about 80%.
- **`mastery`** (0–1) is one number for the profile: the average of the three level rates, 1.0 once mastered.
- Each skill has a **status**:
  - **mastered**: `mastered_at` is set
  - **learning**: mastery 0.5 or more
  - **weak**: below 0.5
  - **unknown**: no row yet
- Once mastered, a skill is **reviewed** later (after 1, 3, 7, 21, then 60 days). Passing a review moves it to the next interval. Failing one restarts the schedule and adds `review_failed`; the skill stays mastered.
- `flags` record what happened to a skill:

| flag | meaning |
|---|---|
| `placement` | set by placement; also marks the student as **placed** |
| `inferred` | not tested, but lies behind a skill passed in placement, so it counts as mastered |
| `gap` | found as a gap; practised until mastered |
| `stuck` | rate under 50% after 5+ answers at the current level, which triggers backward gap detection |
| `review_failed` | failed a retention review |

---

## 3. Flows

### Start → placement → practice
Placement puts each student at the correct **starting point** on the DAG. After that, skills unlock once all their prerequisites are mastered.

1. **Questionnaire:** for each topic (`GET /skills/topics`, curriculum order) the student or teacher answers `dont_know`, `partly` or `well`. The screen is a frontend TODO; the API takes the answers.
   - Nothing known → **beginner**: no test. The student starts at the roots, and their first sheet is already practice.
   - Otherwise the answers give a **window**:
     - **end** = the Gate (or last skill) of the topics answered `partly`/`well`, keeping the outermost ones;
     - **start** = the Gates of the topics answered `well`: what lies behind them is assumed solid;
     - **window** = end + up to 2 prerequisite levels below it (`PLACEMENT_WINDOW_DEPTH`), never going behind start. It's short on purpose.
2. **Placement rounds:** each round is one paper worksheet. Testing starts at end and moves down with gap detection: pass → stop, everything below counts as known; fail → test its prerequisites. Spare room on a sheet is filled with untested skills behind the ones being tested (look-ahead), staying inside the window. Each skill is judged by its smoothed rate over all rounds: ≥ 0.75 clearly passed, ≤ 0.35 clearly failed, in between not sure yet, so it's asked again next round (2 of 2 passes, 0 of 2 fails, 1 of 2 is asked again).
3. **The lower bound moves:** if the bottom of the window fails, the walk keeps going below it until it reaches skills the student passes.
4. After each graded round the walk is **replayed** from all the scores so far. Placement finishes when nothing is left to test, or after 3 rounds.
5. **Finishing placement** writes mastery rows:
   - passed skills → mastered (`placement`)
   - failed skills → low mastery (`placement`, plus `gap` for the deepest ones)
   - untested skills behind passed ones → mastered (`inferred`)
6. From then on the student gets **practice** worksheets.

No extra tables are needed. While a student isn't placed, every graded worksheet counts as a placement round.

### Practice worksheet (no teacher target)
Questions are split by `WORKSHEET_MIX` (default 40% / 40% / 20%):
- **gaps:** skills flagged `gap`, plus, for every `stuck` skill, the gaps and untested prerequisites found by walking back from it;
- **next:** unlocked skills, in soft curriculum order;
- **reviews:** mastered skills whose review is due.

If a group is empty, its share goes to the others.

### Teacher-targeted worksheet
The teacher chooses one or more skills and, optionally:
- `include_weak_prereqs = false` → questions only from the chosen skills;
- otherwise, earlier skills within `max_depth` steps back whose mastery is below `weak_below` are added (weakest first).

The teacher can create the worksheet for **all students in the class or only some**. Each student still gets their own questions.

### Question choice
- **Difficulty** follows the skill's level, mixed with the level below (see Mastery). Placement sheets are all medium (2).
- Questions the student has already seen are avoided until that skill's pool runs out.
- Questions are ordered prerequisites first.

### Grading → mastery
`POST /worksheets/{id}/scores` with one score (0–1) per question position.
- **Placement:** the walk is replayed; if placement is finished, the mastery rows are written.
- **Practice:** each skill's rates are recalculated from its answer history (`worksheet_items` + `questions.difficulty`); level, mastered, review and stuck are updated.

---

## 4. Running it

```bash
pip install -r requirements.txt
python scripts/import_skills.py --file algebra.xlsx --dry-run   # check the sheet, show what would change
python scripts/import_skills.py --file algebra.xlsx             # load it into the DB
uvicorn api.main:app --reload                                   # open http://localhost:8000/docs
```

- **Database:** set with the `DB_URL` environment variable (default `postgresql+psycopg2://postgres:root@localhost:5432/dag`). Create the tables once with `psql -U postgres -d dag -f db/schema.sql`. That file is plain SQL. `skills` and `skill_prerequisites` are copied from the actual DB; the other tables come from the schema design.
- **Frontend URLs:** allowed browser origins are set with `CORS_ORIGINS` (comma separated).
- **Tuning:** every number (level rules, thresholds, review intervals, placement limits, worksheet mix) is in `config/settings.py`.

### Tests
```bash
pytest -q tests                      # logic only, no database needed
TEST_DB_URL=postgresql+psycopg2://postgres:root@localhost:5432/dag_test pytest -q tests
```
The second command also runs the full API flow (placement → practice → teacher targets) on a **throwaway** database. It drops and recreates every table in `TEST_DB_URL`.

---

## 5. API at a glance

| Method & path | What it does |
|---|---|
| `GET /skills` | all skills in curriculum order |
| `GET /skills/topics` | topic names in curriculum order: the placement questionnaire |
| `POST /admin/reload-graph` | reload the graph after an import |
| `GET /students/{id}/profile` | mastery, status and flags per skill, and whether the student is placed |
| `GET /students/{id}/next-skills` | unlocked skills (forward) |
| `GET /students/{id}/path/{target}` | ordered skills to learn to reach a target |
| `GET /students/{id}/gaps/{skill}` | backward gap report for a skill the student is failing |
| `POST /assignments` | create an assignment (class, title, number of questions, due date) |
| `POST /assignments/{id}/worksheets` | generate worksheets: students (default all), settings, placement questionnaire answers |
| `GET /worksheets/{id}` | a worksheet's questions, with skill and difficulty |
| `POST /worksheets/{id}/scores` | submit graded scores, which updates mastery |

Request and response shapes are shown live at `/docs`.

---

## 6. Not built here
- Reading scans and answer boxes (OCR), and grading answers into scores. The engine starts from scores.
- Rendering worksheet PDFs (`worksheets.pdf_url`).
- Authentication and permissions (`users.auth_id`).
