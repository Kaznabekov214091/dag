# Design: placement

**Status:** paper placement is built (window from the questionnaire, beginners skip the test, look-ahead inside the window). The questionnaire screen and online mode are TODO. Note: `start` only shapes round 1; later rounds rebuild the window from its end skills by depth, since nothing is stored.

## 1. What placement is

Placement puts the student at the correct **starting point** on the skill DAG. After that there is
only **practice**: a skill unlocks once all its prerequisites are mastered (`next_skills`).
No diagnostic questions are mixed into practice. The only testing during practice is the existing
`stuck` → backward gap check.

## 2. Who gets placement

| student | what happens |
|---|---|
| true beginner (e.g. K1, nothing learned) | **no placement**. Start at the roots of the DAG. |
| everyone else | placement inside a **window**, then practice |

## 3. The window

- **Input:** a **start** node and an **end** node.
  - **TODO (frontend):** the quick form that produces them. The engine only takes the two nodes
    (or topics resolved to nodes) as input.
- **The window** = the skills between start and end. It exists so placement doesn't test skills
  far from where the student actually is.
- **Testing starts at the end** and moves down with **gap detection** (`gap_walk`):
  - **pass** → stop; everything below it counts as known;
  - **fail** → test its prerequisites, down to solid ground (skills that pass).
  - **confidence:** pass/fail only once the smoothed rate over all rounds is clear (≥ 0.75 / ≤ 0.35); in between the skill is asked again next round.
- **The lower bound moves.** If the walk fails at the bottom of the window, it keeps going below
  `start` until it hits solid ground.
- **Below start, never reached by the walk** → assumed known (inferred).
- **Above end** → not started; unlocks normally in practice.
- **Placement ends** when the walk has nothing left to test, with a safety cap.

## 4. Initial mastery (written when placement ends)

- tested at medium: passed → mastered (level 3); failed → level 1 (flag `placement`);
- failed with all prerequisites passed → also flag `gap`;
- known by inference (below a pass, or below an untouched `start`) → mastered (flag `inferred`);
- above end → no row.

## 5. Two modes, same logic

Both modes run the same window + gap walk. Only the step size and turnaround differ.

### 5a. Paper (the current build, adjusted)
- **One round = one sheet.** The walk moves down one level per graded sheet.
- **Look-ahead** fills spare room on the sheet with the next 1–2 levels below the skills being
  tested, so a long chain of failures doesn't take one sheet per level.
- **Slow:** print → solve → scan → grade, for every round.

### 5b. Online — TODO (not now)
Later; online placement uses **multiple-choice (MCQ)** questions. Notes kept for when it's picked up:

- **One step = one question.** Each answer is checked immediately and the walk is replayed, so
  the next question is chosen with full knowledge of every answer so far. No look-ahead guessing.
- **Finishes in one sitting**, typically in far fewer questions than paper.
- **More data per answer** (e.g. time taken, retries) could later sharpen the initial mastery.

**What online needs that doesn't exist yet:**
1. **Automatic answer checking.** The answer has to be scored the moment it's typed or chosen.
   This depends on the answer format in `questions.answer` (number / expression / multiple
   choice). It's the same work as answer evaluation for scans, minus the OCR.
2. **Endpoints:** start a session (start/end nodes) → next question → submit answer → … → done.
   No session table is needed: answers are stored as items of a worksheet without a PDF, and the
   walk is replayed from them (the same stateless trick as paper).
3. **Young students:** typing math is hard for K-2. Online questions may need multiple choice or
   number-only answers.
4. **Extra data** such as time per answer has no column today. Storing it would be a DB change
   (your decision). Until then, online uses only right/wrong, like paper.

## 6. Open
- The quick form (frontend TODO).
- Online mode with MCQ (TODO).
- Safety cap for paper: max sheets.
