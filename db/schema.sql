-- Adaptive math practice — PostgreSQL schema
--
-- Sources:
--   skills, skill_prerequisites  -> copied from the actual database (already exist there)
--   every other table            -> from the schema design, with one adjustment:
--                                   skill_nodes / skill_edges are not used; the skill graph is
--                                   skills / skill_prerequisites, so node_id references skills(id)

-- ===== Metadata: schools, people, classes =====

CREATE TABLE organizations (
    id          serial PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id          serial PRIMARY KEY,
    org_id      int  NOT NULL REFERENCES organizations(id),
    auth_id     text UNIQUE,    -- ID from your auth provider
    email       text,           -- optional (young students may not have one)
    full_name   text NOT NULL,
    role        text NOT NULL CHECK (role IN ('admin', 'teacher', 'student')),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE classes (
    id           serial PRIMARY KEY,
    org_id       int  NOT NULL REFERENCES organizations(id),
    teacher_id   int  NOT NULL REFERENCES users(id),
    name         text NOT NULL,          -- e.g. '6B Math'
    grade_level  smallint,
    school_year  text NOT NULL           -- e.g. '2026-2027'
);

CREATE TABLE class_students (
    class_id    int NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id  int NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (class_id, student_id)
);

-- ===== Learning engine: skill DAG (as in the actual database) =====
-- Filled by scripts/import_skills.py from the spreadsheet. IF NOT EXISTS: they already exist.

CREATE TABLE IF NOT EXISTS skills (
    id         integer      NOT NULL,
    topic      varchar(100) NOT NULL,
    sub_topic  varchar(100),
    skill      varchar(150) NOT NULL,
    CONSTRAINT skills_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS skill_prerequisites (
    skill_id         integer    NOT NULL,
    prerequisite_id  integer    NOT NULL,
    type             varchar(4) NOT NULL,
    CONSTRAINT skill_prerequisites_pkey PRIMARY KEY (skill_id, prerequisite_id, type),
    CONSTRAINT skill_prerequisites_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES skills(id),
    CONSTRAINT skill_prerequisites_prerequisite_id_fkey FOREIGN KEY (prerequisite_id) REFERENCES skills(id),
    CONSTRAINT skill_prerequisites_type_check CHECK (type IN ('soft', 'hard'))
);

-- ===== Question bank =====

CREATE TABLE questions (
    id          serial PRIMARY KEY,
    node_id     int  NOT NULL REFERENCES skills(id),
    content     jsonb NOT NULL,   -- text, images
    answer      jsonb NOT NULL,
    difficulty  smallint NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3)   -- 1 easy, 2 medium, 3 hard
);

-- ===== Student mastery (adaptive profile) =====

CREATE TABLE student_mastery (
    student_id      int  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_id         int  NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    mastery         real NOT NULL DEFAULT 0 CHECK (mastery BETWEEN 0 AND 1),
    mastered_at     timestamptz,                   -- NULL until mastered
    next_review_at  timestamptz,                   -- NULL until mastered
    review_level    smallint NOT NULL DEFAULT 0,   -- passed retention checks in a row
    difficulty      smallint NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),  -- current level on this node: 1 easy, 2 medium, 3 hard
    flags          text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (student_id, node_id),
    CHECK (next_review_at IS NULL OR mastered_at IS NOT NULL)
);

-- ===== Assignments & worksheets =====

-- Teacher decides WHEN; system decides WHAT each student gets
CREATE TABLE assignments (
    id             serial PRIMARY KEY,
    class_id       int  NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    teacher_id     int  NOT NULL REFERENCES users(id),
    title          text NOT NULL,
    num_questions  smallint NOT NULL DEFAULT 10,
    due_at         timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- One individual worksheet per student per assignment
CREATE TABLE worksheets (
    id             serial PRIMARY KEY,
    assignment_id  int  NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id     int  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status         text NOT NULL DEFAULT 'generated'
                   CHECK (status IN ('generated', 'submitted', 'evaluated')),
    pdf_url        text,          -- generated worksheet
    scan_url       text,          -- uploaded completed worksheet
    created_at     timestamptz NOT NULL DEFAULT now(),
    submitted_at   timestamptz,
    UNIQUE (assignment_id, student_id)
);

-- Questions on a worksheet
CREATE TABLE worksheet_items (
    worksheet_id  int NOT NULL REFERENCES worksheets(id) ON DELETE CASCADE,
    position      smallint NOT NULL,        -- question number
    question_id   int NOT NULL REFERENCES questions(id),
    score         real CHECK (score BETWEEN 0 AND 1),
    feedback      text,
    PRIMARY KEY (worksheet_id, position)
);

-- Answer boxes: each question can have one or more
CREATE TABLE answer_boxes (
    worksheet_id    int NOT NULL,
    position        smallint NOT NULL,
    box_no          smallint NOT NULL,      -- 1, 2, 3 within the question
    page            smallint NOT NULL DEFAULT 1,
    x               real NOT NULL CHECK (x BETWEEN 0 AND 1),  -- fractions of page size
    y               real NOT NULL CHECK (y BETWEEN 0 AND 1),
    w               real NOT NULL CHECK (w BETWEEN 0 AND 1),
    h               real NOT NULL CHECK (h BETWEEN 0 AND 1),
    student_answer  text,                   -- what was read from the box
    PRIMARY KEY (worksheet_id, position, box_no),
    FOREIGN KEY (worksheet_id, position)
        REFERENCES worksheet_items (worksheet_id, position) ON DELETE CASCADE
);
