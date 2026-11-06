import os

# ---------------------------------------------------------
# Database (shared by every module in the project)
# ---------------------------------------------------------
DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://postgres:root@localhost:5432/dag")

# ---------------------------------------------------------
# API
# ---------------------------------------------------------
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# ---------------------------------------------------------
# Skill DAG
# ---------------------------------------------------------
# values of skill_prerequisites.type; one DAG is built per type
DAG_EDGE_TYPES = ("soft", "hard")
GATE_SUB_TOPIC = "Gate"   # skills.sub_topic of a topic's mastery checkpoint

# ---------------------------------------------------------
# Mastery: smoothed correct rate per difficulty level
#   rate = (correct + 1) / (answers + 2) over the last RATE_WINDOW answers at one level
# ---------------------------------------------------------
LEVELS = (1, 2, 3)            # student_mastery.difficulty: 1 easy, 2 medium, 3 hard
RATE_WINDOW = 20              # the rate counts only the last N answers at a level
LEVEL_UP_MIN_ANSWERS = 10     # at least this many answers at the current level ...
LEVEL_UP_RATE = 0.8           # ... and a rate at/above this -> next level (at the top level: mastered)
PREVIOUS_LEVEL_SHARE = 0.3    # at level 2+, this share of a node's questions comes from the level below
STUCK_MIN_ANSWERS = 5         # at least this many answers at the current level ...
STUCK_BELOW = 0.5             # ... and a rate below this -> stuck (backward gap detection)

WEAK_BELOW = 0.5              # mastery number below this = a gap when walking backward

PASS_SCORE = 0.7   # average item score on one skill in one worksheet that counts as passing it (placement, reviews)

# retention reviews: days until the next check, by review_level
REVIEW_INTERVALS_DAYS = (1, 3, 7, 21, 60)

# student_mastery.flags
FLAG_PLACEMENT = "placement"        # set by placement (also marks the student as placed)
FLAG_INFERRED = "inferred"          # mastered by inference: lies behind a skill passed in placement
FLAG_GAP = "gap"                    # found as a gap; practised until mastered
FLAG_STUCK = "stuck"                # rate too low at the current level -> backward gap detection
FLAG_REVIEW_FAILED = "review_failed"

# ---------------------------------------------------------
# Questions
# ---------------------------------------------------------
QUESTIONS_PER_SKILL = 2

# ---------------------------------------------------------
# Placement (beginners skip it and start at the roots)
# ---------------------------------------------------------
PLACEMENT_MAX_ROUNDS = 3
PLACEMENT_DIFFICULTY = 2   # placement asks medium; failed -> practice starts at level 1
PLACEMENT_QUESTIONS_PER_SKILL = 2
PLACEMENT_MAX_SKILLS_PER_ROUND = 8
PLACEMENT_WINDOW_DEPTH = 2   # window = end skills + this many prerequisite levels below them

# ---------------------------------------------------------
# Worksheets
# ---------------------------------------------------------
DEFAULT_NUM_QUESTIONS = 10
DEFAULT_MAX_DEPTH = 2
# share of questions per group when the teacher picks no target skills
WORKSHEET_MIX = {"gaps": 0.4, "next": 0.4, "review": 0.2}
