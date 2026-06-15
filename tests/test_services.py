import sqlite3

import pytest

from exam_system import db, services
from exam_system.config import DEFAULT_ADMIN_MOBILE


def test_init_db_creates_default_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

    db.init_db()

    with sqlite3.connect(db.DB_PATH) as conn:
        admin_row = conn.execute(
            "select mobile, role, status from users where mobile = ?",
            (DEFAULT_ADMIN_MOBILE,),
        ).fetchone()

    assert admin_row == ("admin", "admin", "approved")


def test_init_db_is_idempotent_for_default_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

    db.init_db()
    db.init_db()

    with sqlite3.connect(db.DB_PATH) as conn:
        admin_count = conn.execute(
            "select count(*) from users where mobile = ?",
            (DEFAULT_ADMIN_MOBILE,),
        ).fetchone()[0]

    assert admin_count == 1


def test_init_db_creates_expected_score_column_constraints(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

    db.init_db()

    with sqlite3.connect(db.DB_PATH) as conn:
        table_columns = {
            table: {
                row[1]: {
                    "type": row[2].upper(),
                    "notnull": row[3],
                    "default": row[4],
                }
                for row in conn.execute(f"pragma table_info({table})")
            }
            for table in (
                "papers",
                "questions",
                "exam_attempts",
                "answers",
                "subjective_reviews",
                "practice_attempts",
            )
        }

    assert table_columns["papers"]["total_score"] == {
        "type": "INTEGER",
        "notnull": 1,
        "default": None,
    }
    assert table_columns["questions"]["score"] == {
        "type": "INTEGER",
        "notnull": 1,
        "default": None,
    }
    assert table_columns["exam_attempts"]["objective_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": "0",
    }
    assert table_columns["exam_attempts"]["suggested_subjective_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": "0",
    }
    assert table_columns["exam_attempts"]["final_subjective_score"] == {
        "type": "REAL",
        "notnull": 0,
        "default": None,
    }
    assert table_columns["exam_attempts"]["final_score"] == {
        "type": "REAL",
        "notnull": 0,
        "default": None,
    }
    assert table_columns["answers"]["auto_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": "0",
    }
    assert table_columns["answers"]["suggested_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": "0",
    }
    assert table_columns["answers"]["final_score"] == {
        "type": "REAL",
        "notnull": 0,
        "default": None,
    }
    assert table_columns["subjective_reviews"]["suggested_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": None,
    }
    assert table_columns["subjective_reviews"]["final_score"] == {
        "type": "REAL",
        "notnull": 1,
        "default": None,
    }
    assert table_columns["practice_attempts"]["is_correct"] == {
        "type": "INTEGER",
        "notnull": 0,
        "default": None,
    }


def test_connect_enforces_foreign_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

    db.init_db()

    with pytest.raises(sqlite3.IntegrityError):
        with db.connect() as conn:
            conn.execute(
                """
                insert into questions (
                    paper_id,
                    question_type,
                    order_no,
                    stem,
                    score
                )
                values (?, ?, ?, ?, ?)
                """,
                (999, "single_choice", 1, "Question", 2),
            )


def test_connect_rolls_back_on_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")

    db.init_db()

    password_hash, password_salt = db.hash_password("password")

    with pytest.raises(RuntimeError):
        with db.connect() as conn:
            conn.execute(
                """
                insert into users (
                    name,
                    mobile,
                    password_hash,
                    password_salt,
                    role,
                    status,
                    created_at
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "Rollback User",
                    "rollback-user",
                    password_hash,
                    password_salt,
                    "employee",
                    "pending",
                    "2026-06-12T00:00:00",
                ),
            )
            raise RuntimeError("force rollback")

    with sqlite3.connect(db.DB_PATH) as conn:
        user_count = conn.execute(
            "select count(*) from users where mobile = ?",
            ("rollback-user",),
        ).fetchone()[0]

    assert user_count == 0


def _setup_service_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()


def _sample_papers():
    return [
        {
            "title": "Sample Paper",
            "duration_minutes": 50,
            "total_score": 100,
            "questions": [
                {
                    "question_type": "single_choice",
                    "order_no": 1,
                    "type_order": 1,
                    "stem": "Question 1",
                    "options": [{"key": "A", "text": "Wrong"}, {"key": "B", "text": "Right"}],
                    "correct_answer": "B",
                    "reference_answer": "",
                    "keywords": "",
                    "score": 2,
                },
                {
                    "question_type": "short_answer",
                    "order_no": 2,
                    "type_order": 1,
                    "stem": "Short answer",
                    "options": [],
                    "correct_answer": "",
                    "reference_answer": "审批 库存",
                    "keywords": "审批,库存",
                    "score": 7,
                },
            ],
        }
    ]


def _multi_papers():
    papers = []
    for paper_no in range(1, 4):
        papers.append(
            {
                "title": f"Sample Paper {paper_no}",
                "duration_minutes": 50,
                "total_score": 10,
                "questions": [
                    {
                        "question_type": "single_choice",
                        "order_no": 1,
                        "type_order": 1,
                        "stem": f"Question {paper_no}-1",
                        "options": [{"key": "A", "text": "Wrong"}, {"key": "B", "text": "Right"}],
                        "correct_answer": "B",
                        "reference_answer": "",
                        "keywords": "",
                        "score": 2,
                    },
                    {
                        "question_type": "single_choice",
                        "order_no": 2,
                        "type_order": 2,
                        "stem": f"Question {paper_no}-2",
                        "options": [{"key": "A", "text": "Right"}, {"key": "B", "text": "Wrong"}],
                        "correct_answer": "A",
                        "reference_answer": "",
                        "keywords": "",
                        "score": 2,
                    },
                ],
            }
        )
    return papers


def test_current_exam_paper_can_be_selected_by_admin(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)
    services.seed_papers(_multi_papers())
    papers = services.list_papers()

    assert services.get_current_exam_paper()["id"] == papers[0]["id"]

    services.set_current_exam_paper(papers[1]["id"])

    assert services.get_current_exam_paper()["id"] == papers[1]["id"]


def test_current_exam_paper_rejects_missing_paper(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)
    services.seed_papers(_sample_papers())

    with pytest.raises(ValueError, match="Paper not found"):
        services.set_current_exam_paper(999)


def test_random_practice_questions_sample_from_all_papers(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)
    services.seed_papers(_multi_papers())
    calls = []

    def fake_sample(items, limit):
        calls.append((len(items), limit))
        return list(reversed(items))[:limit]

    monkeypatch.setattr(services.random, "sample", fake_sample)

    questions = services.get_random_practice_questions(limit=3)

    assert calls == [(6, 3)]
    assert len(questions) == 3
    assert [question["stem"] for question in questions] == [
        "Question 3-2",
        "Question 3-1",
        "Question 2-2",
    ]
    assert all("options" in question for question in questions)


def test_register_user_starts_pending_and_can_be_approved(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)

    user_id = services.register_user(
        "Zhang San",
        "13800000000",
        "pw",
        "East",
        "Project A",
        "Material Manager",
    )
    pending = services.get_user_by_mobile("13800000000")

    assert pending["id"] == user_id
    assert pending["status"] == "pending"
    assert pending["role"] == "employee"

    services.set_user_status(user_id, "approved")
    approved = services.get_user_by_mobile("13800000000")

    assert approved["status"] == "approved"


def test_seed_papers_and_submit_attempt_scores_objective_and_subjective(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)
    services.seed_papers(_sample_papers())
    user_id = services.register_user("Li Si", "13900000000", "pw", "East", "Project B", "Clerk")
    services.set_user_status(user_id, "approved")

    paper = services.list_papers()[0]
    questions = services.get_paper_questions(paper["id"])
    attempt_id = services.start_attempt(user_id, paper["id"])
    services.submit_attempt(
        attempt_id,
        {
            str(questions[0]["id"]): "B",
            str(questions[1]["id"]): "审批",
        },
    )

    attempt = services.get_attempt(attempt_id)

    assert attempt["status"] == "pending_review"
    assert attempt["objective_score"] == 2
    assert attempt["suggested_subjective_score"] == 3.5


def test_review_answer_completes_attempt_and_final_score(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)
    services.seed_papers(_sample_papers())
    user_id = services.register_user("Wang Wu", "13700000000", "pw", "East", "Project C", "Clerk")
    services.set_user_status(user_id, "approved")
    admin = services.get_user_by_mobile(DEFAULT_ADMIN_MOBILE)
    paper = services.list_papers()[0]
    questions = services.get_paper_questions(paper["id"])
    attempt_id = services.start_attempt(user_id, paper["id"])
    services.submit_attempt(
        attempt_id,
        {
            str(questions[0]["id"]): "B",
            str(questions[1]["id"]): "审批",
        },
    )
    pending = services.list_pending_reviews()

    services.review_answer(pending[0]["answer_id"], admin["id"], 6, "ok")
    attempt = services.get_attempt(attempt_id)

    assert attempt["status"] == "completed"
    assert attempt["final_subjective_score"] == 6
    assert attempt["final_score"] == 8


def test_ensure_papers_seeded_imports_complete_available_papers_from_truncated_docx(tmp_path, monkeypatch):
    _setup_service_db(tmp_path, monkeypatch)

    status = services.ensure_papers_seeded()
    papers = services.list_papers()

    assert status["seeded"] is True
    assert status["paper_count"] == 4
    assert "paper 5" in status["warning"]
    assert len(papers) == 4
