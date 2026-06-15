"""Application service functions for users, papers, attempts, and results."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import BASE_DIR
from .docx_importer import parse_available_docx, parse_docx
from .grading import grade_objective, suggest_subjective_score

OBJECTIVE_TYPES = {"single_choice", "multiple_choice", "true_false"}
SUBJECTIVE_TYPES = {"short_answer", "case_analysis"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dict(row):
    return dict(row) if row is not None else None


def register_user(name, mobile, password, region, project, position) -> int:
    with db.connect() as conn:
        password_hash, password_salt = db.hash_password(password)
        cursor = conn.execute(
            """
            insert into users
            (name, mobile, password_hash, password_salt, role, status, region, project, position, created_at)
            values (?, ?, ?, ?, 'employee', 'pending', ?, ?, ?, ?)
            """,
            (
                name.strip(),
                mobile.strip(),
                password_hash,
                password_salt,
                region.strip(),
                project.strip(),
                position.strip(),
                _now(),
            ),
        )
        return int(cursor.lastrowid)


def get_user_by_mobile(mobile) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("select * from users where mobile = ?", (mobile,)).fetchone()
    return _dict(row)


def get_user(user_id) -> dict | None:
    with db.connect() as conn:
        row = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
    return _dict(row)


def set_user_status(user_id, status) -> None:
    if status not in {"pending", "approved", "rejected"}:
        raise ValueError(f"Invalid user status: {status}")
    with db.connect() as conn:
        conn.execute("update users set status = ? where id = ?", (status, user_id))


def list_users(status=None, region=None, project=None, position=None, keyword=None) -> list[dict]:
    clauses = []
    params = []
    for field, value in (
        ("status", status),
        ("region", region),
        ("project", project),
        ("position", position),
    ):
        if value:
            clauses.append(f"{field} = ?")
            params.append(value)
    if keyword:
        clauses.append("(name like ? or mobile like ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    where = f"where {' and '.join(clauses)}" if clauses else ""
    with db.connect() as conn:
        rows = conn.execute(f"select * from users {where} order by created_at desc", params).fetchall()
    return [dict(row) for row in rows]


def seed_papers(papers: list[dict]) -> None:
    with db.connect() as conn:
        for table in (
            "subjective_reviews",
            "answers",
            "exam_attempts",
            "practice_attempts",
            "question_options",
            "questions",
            "papers",
        ):
            conn.execute(f"delete from {table}")
        conn.execute("delete from app_settings where key = 'current_exam_paper_id'")

        for paper in papers:
            cursor = conn.execute(
                "insert into papers (title, duration_minutes, total_score) values (?, ?, ?)",
                (paper["title"], paper["duration_minutes"], paper["total_score"]),
            )
            paper_id = int(cursor.lastrowid)
            for question in paper["questions"]:
                question_cursor = conn.execute(
                    """
                    insert into questions
                    (paper_id, question_type, order_no, stem, correct_answer, reference_answer, keywords, score)
                    values (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper_id,
                        question["question_type"],
                        question["order_no"],
                        question["stem"],
                        question.get("correct_answer", ""),
                        question.get("reference_answer", ""),
                        question.get("keywords", ""),
                        question["score"],
                    ),
                )
                question_id = int(question_cursor.lastrowid)
                for option in question.get("options", []):
                    conn.execute(
                        """
                        insert into question_options (question_id, option_key, option_text)
                        values (?, ?, ?)
                        """,
                        (question_id, option["key"], option["text"]),
                    )


def ensure_papers_seeded() -> dict:
    existing = list_papers()
    if existing:
        return {"seeded": False, "paper_count": len(existing), "warning": ""}

    docx_files = sorted(Path(BASE_DIR).glob("*.docx"))
    if not docx_files:
        return {"seeded": False, "paper_count": 0, "warning": "No .docx source file found."}

    warning = ""
    try:
        papers = parse_docx(docx_files[0])
    except ValueError:
        papers, warning = parse_available_docx(docx_files[0])

    seed_papers(papers)
    return {"seeded": True, "paper_count": len(papers), "warning": warning}


def list_papers() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute("select * from papers order by id").fetchall()
    return [dict(row) for row in rows]


def set_current_exam_paper(paper_id) -> None:
    with db.connect() as conn:
        paper = conn.execute("select id from papers where id = ?", (paper_id,)).fetchone()
        if paper is None:
            raise ValueError(f"Paper not found: {paper_id}")
        conn.execute(
            """
            insert into app_settings (key, value)
            values ('current_exam_paper_id', ?)
            on conflict(key) do update set value = excluded.value
            """,
            (str(paper_id),),
        )


def get_current_exam_paper() -> dict | None:
    with db.connect() as conn:
        setting = conn.execute(
            "select value from app_settings where key = 'current_exam_paper_id'"
        ).fetchone()
        paper = None
        if setting:
            paper = conn.execute("select * from papers where id = ?", (setting["value"],)).fetchone()
        if paper is None:
            paper = conn.execute("select * from papers order by id limit 1").fetchone()
    return _dict(paper)


def get_paper_questions(paper_id) -> list[dict]:
    with db.connect() as conn:
        question_rows = conn.execute(
            "select * from questions where paper_id = ? order by order_no",
            (paper_id,),
        ).fetchall()
        questions = []
        for row in question_rows:
            question = dict(row)
            options = conn.execute(
                """
                select option_key as key, option_text as text
                from question_options
                where question_id = ?
                order by option_key
                """,
                (question["id"],),
            ).fetchall()
            question["options"] = [dict(option) for option in options]
            questions.append(question)
    return questions


def get_questions_by_ids(question_ids) -> list[dict]:
    ids = [int(question_id) for question_id in question_ids]
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    with db.connect() as conn:
        rows = conn.execute(
            f"select * from questions where id in ({placeholders})",
            ids,
        ).fetchall()
        questions_by_id = {row["id"]: dict(row) for row in rows}
        for question in questions_by_id.values():
            options = conn.execute(
                """
                select option_key as key, option_text as text
                from question_options
                where question_id = ?
                order by option_key
                """,
                (question["id"],),
            ).fetchall()
            question["options"] = [dict(option) for option in options]
    return [questions_by_id[question_id] for question_id in ids if question_id in questions_by_id]


def get_random_practice_questions(limit=20) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute("select id from questions order by id").fetchall()
    question_ids = [row["id"] for row in rows]
    selected_ids = random.sample(question_ids, min(limit, len(question_ids)))
    return get_questions_by_ids(selected_ids)


def start_attempt(user_id, paper_id) -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            insert into exam_attempts (user_id, paper_id, status, started_at)
            values (?, ?, 'in_progress', ?)
            """,
            (user_id, paper_id, _now()),
        )
        return int(cursor.lastrowid)


def submit_attempt(attempt_id, answers: dict[str, str]) -> None:
    attempt = get_attempt(attempt_id)
    questions = get_paper_questions(attempt["paper_id"])
    objective_score = 0.0
    suggested_subjective_score = 0.0
    has_subjective = False

    with db.connect() as conn:
        for question in questions:
            answer_text = answers.get(str(question["id"]), "")
            auto_score = 0.0
            suggested_score = 0.0
            if question["question_type"] in OBJECTIVE_TYPES:
                auto_score = grade_objective(
                    question["question_type"],
                    answer_text,
                    question["correct_answer"],
                    question["score"],
                )
                objective_score += auto_score
            else:
                has_subjective = True
                suggested_score, _hits = suggest_subjective_score(
                    answer_text,
                    question["keywords"],
                    question["score"],
                )
                suggested_subjective_score += suggested_score

            conn.execute(
                """
                insert into answers
                (attempt_id, question_id, answer_text, auto_score, suggested_score)
                values (?, ?, ?, ?, ?)
                on conflict(attempt_id, question_id)
                do update set
                    answer_text = excluded.answer_text,
                    auto_score = excluded.auto_score,
                    suggested_score = excluded.suggested_score
                """,
                (attempt_id, question["id"], answer_text, auto_score, suggested_score),
            )

        status = "pending_review" if has_subjective else "completed"
        final_score = None if has_subjective else objective_score
        final_subjective_score = None if has_subjective else 0.0
        conn.execute(
            """
            update exam_attempts
            set status = ?,
                objective_score = ?,
                suggested_subjective_score = ?,
                final_subjective_score = ?,
                final_score = ?,
                submitted_at = ?
            where id = ?
            """,
            (
                status,
                objective_score,
                suggested_subjective_score,
                final_subjective_score,
                final_score,
                _now(),
                attempt_id,
            ),
        )


def get_attempt(attempt_id) -> dict:
    with db.connect() as conn:
        row = conn.execute("select * from exam_attempts where id = ?", (attempt_id,)).fetchone()
    if row is None:
        raise ValueError(f"Attempt not found: {attempt_id}")
    return dict(row)


def list_user_attempts(user_id) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            select a.*, p.title as paper_title
            from exam_attempts a
            join papers p on p.id = a.paper_id
            where a.user_id = ?
            order by a.started_at desc
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_pending_reviews() -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            select
                ans.id as answer_id,
                ans.answer_text,
                ans.suggested_score,
                q.stem,
                q.reference_answer,
                q.keywords,
                q.score as question_score,
                a.id as attempt_id,
                p.title as paper_title,
                u.name as user_name,
                u.mobile
            from answers ans
            join questions q on q.id = ans.question_id
            join exam_attempts a on a.id = ans.attempt_id
            join papers p on p.id = a.paper_id
            join users u on u.id = a.user_id
            where q.question_type in ('short_answer', 'case_analysis')
              and ans.final_score is null
            order by a.submitted_at, ans.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def review_answer(answer_id, reviewer_id, final_score, comment="") -> None:
    with db.connect() as conn:
        row = conn.execute(
            """
            select ans.*, q.score as question_score, a.id as attempt_id
            from answers ans
            join questions q on q.id = ans.question_id
            join exam_attempts a on a.id = ans.attempt_id
            where ans.id = ?
            """,
            (answer_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Answer not found: {answer_id}")
        if final_score < 0 or final_score > row["question_score"]:
            raise ValueError("Final score is outside the question score range.")

        conn.execute(
            """
            insert into subjective_reviews
            (answer_id, reviewer_id, suggested_score, final_score, comment, reviewed_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (answer_id, reviewer_id, row["suggested_score"], final_score, comment, _now()),
        )
        conn.execute(
            "update answers set final_score = ? where id = ?",
            (final_score, answer_id),
        )

        attempt_id = row["attempt_id"]
        remaining = conn.execute(
            """
            select count(*)
            from answers ans
            join questions q on q.id = ans.question_id
            where ans.attempt_id = ?
              and q.question_type in ('short_answer', 'case_analysis')
              and ans.final_score is null
            """,
            (attempt_id,),
        ).fetchone()[0]
        if remaining == 0:
            subjective_total = conn.execute(
                """
                select coalesce(sum(ans.final_score), 0)
                from answers ans
                join questions q on q.id = ans.question_id
                where ans.attempt_id = ?
                  and q.question_type in ('short_answer', 'case_analysis')
                """,
                (attempt_id,),
            ).fetchone()[0]
            attempt = conn.execute(
                "select objective_score from exam_attempts where id = ?",
                (attempt_id,),
            ).fetchone()
            final_total = float(attempt["objective_score"]) + float(subjective_total)
            conn.execute(
                """
                update exam_attempts
                set status = 'completed',
                    final_subjective_score = ?,
                    final_score = ?
                where id = ?
                """,
                (subjective_total, final_total, attempt_id),
            )


def list_results(filters: dict) -> list[dict]:
    clauses = []
    params = []
    mapping = {
        "region": "u.region",
        "project": "u.project",
        "position": "u.position",
        "paper_id": "a.paper_id",
        "status": "a.status",
    }
    for key, column in mapping.items():
        value = filters.get(key) if filters else None
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    keyword = filters.get("keyword") if filters else None
    if keyword:
        clauses.append("(u.name like ? or u.mobile like ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    where = f"where {' and '.join(clauses)}" if clauses else ""
    with db.connect() as conn:
        rows = conn.execute(
            f"""
            select
                a.*,
                p.title as paper_title,
                u.name as user_name,
                u.mobile,
                u.region,
                u.project,
                u.position
            from exam_attempts a
            join papers p on p.id = a.paper_id
            join users u on u.id = a.user_id
            {where}
            order by a.submitted_at desc, a.started_at desc
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]
