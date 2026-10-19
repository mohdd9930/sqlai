"""Builds the sample 'Group Mobility' SQLite database used by the AskData prototype.

Models the internal-mobility hiring funnel: an application moves through
screening -> assessment -> interview -> decision -> offered -> joined, or
drops out as 'rejected' at any point. Interview verdicts (select/reject) are
recorded per round in a separate interview_feedback table; joining_date is
only set once an application reaches 'joined'.

Run with: python -m askdata.data.seed_db
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from askdata.config import DB_PATH

SUBSIDIARIES = ["Axis Finance", "Axis AMC", "Axis Capital", "Axis Securities", "Axis Trustee"]
DEPARTMENTS = ["Technology", "Operations", "Risk", "Sales", "HR", "Finance"]
JOB_TITLES = [
    "Senior Software Engineer", "Data Analyst", "Product Manager", "Operations Lead",
    "Risk Associate", "Relationship Manager", "HR Business Partner", "Finance Controller",
]
FIRST_NAMES = ["Aarav", "Vivaan", "Aditi", "Diya", "Kabir", "Ishaan", "Ananya", "Meera",
               "Rohan", "Sanya", "Arjun", "Priya", "Karan", "Neha", "Rahul", "Pooja"]
LAST_NAMES = ["Sharma", "Verma", "Iyer", "Nair", "Gupta", "Reddy", "Mehta", "Chauhan"]
INTERVIEWERS = ["Ritu Kapoor", "Sandeep Rao", "Meenal Joshi", "Alok Verma",
                "Priyanka Das", "Vikram Nair", "Sunita Rao", "Manish Bhatt"]
SELECT_COMMENTS = ["Strong technical fundamentals", "Good culture fit", "Clear communication",
                    "Solid problem-solving approach", "Impressive domain knowledge"]
REJECT_COMMENTS = ["Communication gaps", "Lacked hands-on depth", "Not aligned with role level",
                    "Inconsistent answers", "Below bar on problem-solving"]

# Funnel: how far each application gets. Weights are illustrative, not tuned to any real data.
STAGE_WEIGHTS = {
    "screening": 0.12,   # still sitting at screening, no decision yet
    "assessment": 0.10,  # passed screening, still at assessment
    "interview": 0.13,   # passed assessment, at interview (may or may not have feedback yet)
    "decision": 0.08,    # passed interview, awaiting hiring decision
    "offered": 0.12,     # decision made, offer extended, not yet joined
    "joined": 0.25,      # offer accepted and joined
    "rejected": 0.20,    # dropped out at some point in the funnel
}
STAGE_ORDER = ["screening", "assessment", "interview", "decision", "offered", "joined", "rejected"]
STAGES_WITH_COMPLETED_INTERVIEW = {"decision", "offered", "joined"}


def _make_interview_rounds(cur, application_id: int, interview_date: date, passed: bool) -> None:
    n_rounds = random.randint(1, 3) if passed else random.randint(1, 2)
    for round_number in range(1, n_rounds + 1):
        is_last = round_number == n_rounds
        if passed:
            result = "select"
        else:
            # only the final round has to be a reject; earlier ones may have been a select
            result = "reject" if is_last else random.choice(["select", "reject"])
        comment = random.choice(SELECT_COMMENTS if result == "select" else REJECT_COMMENTS)
        round_date = (interview_date + timedelta(days=(round_number - 1) * 3)).isoformat()
        cur.execute(
            """INSERT INTO interview_feedback
               (application_id, round_number, interviewer, interview_date, result, comments)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (application_id, round_number, random.choice(INTERVIEWERS), round_date, result, comment),
        )


def build(seed: int = 42) -> None:
    random.seed(seed)
    db_path = Path(DB_PATH)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE subsidiaries (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            subsidiary_id INTEGER NOT NULL REFERENCES subsidiaries(id)
        );

        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            gender TEXT NOT NULL CHECK (gender IN ('M', 'F', 'O')),
            subsidiary_id INTEGER NOT NULL REFERENCES subsidiaries(id)
        );

        CREATE TABLE applications (
            id INTEGER PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            applied_date TEXT NOT NULL,
            stage TEXT NOT NULL CHECK (
                stage IN ('screening','assessment','interview','decision','offered','joined','rejected')
            ),
            joining_date TEXT
        );

        CREATE TABLE interview_feedback (
            id INTEGER PRIMARY KEY,
            application_id INTEGER NOT NULL REFERENCES applications(id),
            round_number INTEGER NOT NULL,
            interviewer TEXT NOT NULL,
            interview_date TEXT NOT NULL,
            result TEXT NOT NULL CHECK (result IN ('select', 'reject')),
            comments TEXT
        );
        """
    )

    sub_ids = []
    for name in SUBSIDIARIES:
        cur.execute("INSERT INTO subsidiaries (name) VALUES (?)", (name,))
        sub_ids.append(cur.lastrowid)

    job_ids = []
    for _ in range(40):
        title = random.choice(JOB_TITLES)
        dept = random.choice(DEPARTMENTS)
        sub_id = random.choice(sub_ids)
        cur.execute(
            "INSERT INTO jobs (title, department, subsidiary_id) VALUES (?, ?, ?)",
            (title, dept, sub_id),
        )
        job_ids.append(cur.lastrowid)

    employee_ids = []
    for _ in range(300):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        dept = random.choice(DEPARTMENTS)
        gender = random.choices(["M", "F", "O"], weights=[0.55, 0.42, 0.03])[0]
        sub_id = random.choice(sub_ids)
        cur.execute(
            "INSERT INTO employees (name, department, gender, subsidiary_id) VALUES (?, ?, ?, ?)",
            (name, dept, gender, sub_id),
        )
        employee_ids.append(cur.lastrowid)

    today = date.today()
    start = today - timedelta(days=400)
    stage_names = list(STAGE_WEIGHTS.keys())
    stage_weights = list(STAGE_WEIGHTS.values())
    interview_feedback_count = 0

    for _ in range(1500):
        employee_id = random.choice(employee_ids)
        job_id = random.choice(job_ids)
        offset = random.randint(0, (today - start).days)
        applied_date = start + timedelta(days=offset)
        stage = random.choices(stage_names, weights=stage_weights)[0]

        joining_date = None
        if stage == "joined":
            join_offset = random.randint(30, 90)
            joining_date = min(applied_date + timedelta(days=join_offset), today).isoformat()

        cur.execute(
            """INSERT INTO applications (employee_id, job_id, applied_date, stage, joining_date)
               VALUES (?, ?, ?, ?, ?)""",
            (employee_id, job_id, applied_date.isoformat(), stage, joining_date),
        )
        application_id = cur.lastrowid

        # Interview feedback exists once an application has actually sat an interview:
        # always for anyone who progressed past it, and for ~40% of rejections (the rest
        # dropped out earlier, at screening or assessment, before ever interviewing).
        reached_interview_stage = stage in STAGES_WITH_COMPLETED_INTERVIEW
        interviewed_then_rejected = stage == "rejected" and random.random() < 0.4
        still_awaiting_feedback = stage == "interview" and random.random() < 0.5

        if reached_interview_stage or interviewed_then_rejected:
            interview_date = applied_date + timedelta(days=random.randint(10, 25))
            passed = reached_interview_stage
            _make_interview_rounds(cur, application_id, interview_date, passed)
            interview_feedback_count += cur.rowcount if cur.rowcount > 0 else 0
        elif stage == "interview" and not still_awaiting_feedback:
            interview_date = applied_date + timedelta(days=random.randint(10, 25))
            _make_interview_rounds(cur, application_id, interview_date, passed=True)

    conn.commit()

    total_feedback = cur.execute("SELECT COUNT(*) FROM interview_feedback").fetchone()[0]
    conn.close()
    print(f"Seeded {db_path} with {len(sub_ids)} subsidiaries, {len(job_ids)} jobs, "
          f"{len(employee_ids)} employees, 1500 applications, {total_feedback} interview_feedback rows.")


if __name__ == "__main__":
    build()
