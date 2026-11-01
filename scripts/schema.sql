-- OLTP source schema: normalized OULAD tables, mirroring the source CSVs.
-- Indexing follows a "realistically administered OLTP system" rule: primary
-- keys and foreign-key/lookup columns are indexed; nothing is added here to
-- specifically speed up the analytical benchmark query (see design doc).

DROP TABLE IF EXISTS student_vle CASCADE;
DROP TABLE IF EXISTS student_assessment CASCADE;
DROP TABLE IF EXISTS student_registration CASCADE;
DROP TABLE IF EXISTS student_info CASCADE;
DROP TABLE IF EXISTS vle CASCADE;
DROP TABLE IF EXISTS assessments CASCADE;
DROP TABLE IF EXISTS courses CASCADE;

CREATE TABLE courses (
    code_module                VARCHAR(10) NOT NULL,
    code_presentation          VARCHAR(10) NOT NULL,
    module_presentation_length INTEGER,
    PRIMARY KEY (code_module, code_presentation)
);

CREATE TABLE assessments (
    id_assessment      INTEGER PRIMARY KEY,
    code_module        VARCHAR(10) NOT NULL,
    code_presentation  VARCHAR(10) NOT NULL,
    assessment_type    VARCHAR(10),
    date                INTEGER,
    weight              NUMERIC,
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);
CREATE INDEX idx_assessments_course ON assessments (code_module, code_presentation);

CREATE TABLE vle (
    id_site             INTEGER PRIMARY KEY,
    code_module         VARCHAR(10) NOT NULL,
    code_presentation   VARCHAR(10) NOT NULL,
    activity_type       VARCHAR(30),
    week_from           INTEGER,
    week_to             INTEGER,
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);
CREATE INDEX idx_vle_course ON vle (code_module, code_presentation);

CREATE TABLE student_info (
    code_module            VARCHAR(10) NOT NULL,
    code_presentation      VARCHAR(10) NOT NULL,
    id_student             INTEGER NOT NULL,
    gender                 VARCHAR(5),
    region                 VARCHAR(50),
    highest_education      VARCHAR(50),
    imd_band                VARCHAR(10),
    age_band                VARCHAR(10),
    num_of_prev_attempts    INTEGER,
    studied_credits        INTEGER,
    disability             VARCHAR(5),
    final_result            VARCHAR(20),
    PRIMARY KEY (code_module, code_presentation, id_student),
    FOREIGN KEY (code_module, code_presentation) REFERENCES courses (code_module, code_presentation)
);
CREATE INDEX idx_student_info_student ON student_info (id_student);

CREATE TABLE student_registration (
    code_module            VARCHAR(10) NOT NULL,
    code_presentation      VARCHAR(10) NOT NULL,
    id_student             INTEGER NOT NULL,
    date_registration       INTEGER,
    date_unregistration     INTEGER,
    PRIMARY KEY (code_module, code_presentation, id_student),
    FOREIGN KEY (code_module, code_presentation, id_student)
        REFERENCES student_info (code_module, code_presentation, id_student)
);

CREATE TABLE student_assessment (
    id_assessment   INTEGER NOT NULL,
    id_student      INTEGER NOT NULL,
    date_submitted  INTEGER,
    is_banked       BOOLEAN,
    score           NUMERIC,
    PRIMARY KEY (id_assessment, id_student),
    FOREIGN KEY (id_assessment) REFERENCES assessments (id_assessment)
);
CREATE INDEX idx_student_assessment_student ON student_assessment (id_student);

-- Large fact-shaped table (~10.6M rows). No FK constraints (ingest-throughput
-- tradeoff for a high-volume log-style table); indexed on the columns an OLTP
-- app would actually look rows up by, not on anything that specifically
-- accelerates the benchmark's aggregate query.
CREATE TABLE student_vle (
    id                  BIGSERIAL PRIMARY KEY,
    code_module         VARCHAR(10) NOT NULL,
    code_presentation   VARCHAR(10) NOT NULL,
    id_student          INTEGER NOT NULL,
    id_site             INTEGER NOT NULL,
    date                INTEGER,
    sum_click           INTEGER
);
