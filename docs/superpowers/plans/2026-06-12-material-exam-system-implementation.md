# Material Exam System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Flask + SQLite web exam system for material management training, with employee registration, admin approval, practice, timed exams, grading, subjective review, result query, CSV export, and responsive desktop/mobile UI.

**Architecture:** Use a small Flask application with clear service modules. Store persistent data in SQLite. Parse the provided `.docx` from the project root into structured papers and questions, then expose server-rendered pages plus JSON endpoints where useful.

**Tech Stack:** Python 3, Flask, Jinja2 templates, SQLite, python-docx, pytest, vanilla JavaScript, responsive CSS.

---

## File Structure

- Create: `app.py` - Flask app factory, routes registration, local server entry point.
- Create: `exam_system/__init__.py` - package marker.
- Create: `exam_system/config.py` - paths, admin defaults, exam constants.
- Create: `exam_system/db.py` - SQLite connection, schema creation, seed entrypoint.
- Create: `exam_system/docx_importer.py` - parse project-root `.docx` into paper/question data.
- Create: `exam_system/auth.py` - password hashing, login session helpers, role guards.
- Create: `exam_system/grading.py` - objective grading and subjective suggested scoring.
- Create: `exam_system/services.py` - user, paper, attempt, review, and result operations.
- Create: `templates/base.html` - shared responsive shell and navigation.
- Create: `templates/login.html`
- Create: `templates/register.html`
- Create: `templates/pending.html`
- Create: `templates/employee_home.html`
- Create: `templates/practice.html`
- Create: `templates/exam.html`
- Create: `templates/results.html`
- Create: `templates/admin_dashboard.html`
- Create: `templates/admin_users.html`
- Create: `templates/admin_papers.html`
- Create: `templates/admin_review.html`
- Create: `templates/admin_results.html`
- Create: `static/styles.css` - desktop and mobile UI.
- Create: `static/app.js` - timer, answer saving, mobile navigation helpers.
- Create: `tests/test_docx_importer.py`
- Create: `tests/test_grading.py`
- Create: `tests/test_services.py`
- Create: `README.md` - run instructions and default admin account.

Repository note: this directory is not a git repository right now. Commit steps below should be skipped unless git is initialized later by the user.

---

### Task 1: Project Skeleton And Configuration

**Files:**
- Create: `exam_system/__init__.py`
- Create: `exam_system/config.py`
- Create: `app.py`
- Create: `README.md`

- [ ] **Step 1: Write the package marker**

Create `exam_system/__init__.py`:

```python
"""Material exam system package."""
```

- [ ] **Step 2: Write configuration**

Create `exam_system/config.py`:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "exam_system.sqlite3"

DEFAULT_ADMIN_MOBILE = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_NAME = "系统管理员"

EXAM_DURATION_MINUTES = 50
PASSING_SCORE = 60

QUESTION_SCORES = {
    "single_choice": 2,
    "multiple_choice": 3,
    "true_false": 1,
    "short_answer": 7,
    "case_analysis": 15,
}
```

- [ ] **Step 3: Write app entrypoint**

Create `app.py`:

```python
from flask import Flask, redirect, url_for

from exam_system.db import init_db


def create_app():
    app = Flask(__name__)
    app.secret_key = "local-dev-change-before-server-deploy"
    init_db()

    @app.get("/")
    def index():
        return redirect(url_for("login"))

    @app.get("/login")
    def login():
        return "login page will be added in Task 6"

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
```

- [ ] **Step 4: Write run instructions**

Create `README.md`:

```markdown
# Material Exam System

Local training and exam system for project material management roles.

## Run

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
```

Open `http://127.0.0.1:5000`.

Default administrator:

- Mobile: `admin`
- Password: `admin123`
```

- [ ] **Step 5: Run smoke command**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m py_compile app.py exam_system\config.py
```

Expected: command exits with code 0.

---

### Task 2: Database Schema And Default Admin

**Files:**
- Create: `exam_system/db.py`
- Modify: `app.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: Write failing database test**

Create `tests/test_services.py`:

```python
import sqlite3

from exam_system import db


def test_init_db_creates_default_admin(tmp_path, monkeypatch):
    test_db = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)

    db.init_db()

    with sqlite3.connect(test_db) as conn:
        row = conn.execute(
            "select mobile, role, status from users where mobile = ?",
            ("admin",),
        ).fetchone()

    assert row == ("admin", "admin", "approved")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_services.py -v
```

Expected: FAIL because `exam_system.db` does not exist.

- [ ] **Step 3: Implement schema and admin seed**

Create `exam_system/db.py`:

```python
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .config import (
    DATA_DIR,
    DB_PATH,
    DEFAULT_ADMIN_MOBILE,
    DEFAULT_ADMIN_NAME,
    DEFAULT_ADMIN_PASSWORD,
)


SCHEMA = """
create table if not exists users (
    id integer primary key autoincrement,
    name text not null,
    mobile text not null unique,
    password_hash text not null,
    role text not null check(role in ('employee', 'admin')),
    status text not null check(status in ('pending', 'approved', 'rejected')),
    region text,
    project text,
    position text,
    created_at text not null
);

create table if not exists papers (
    id integer primary key autoincrement,
    title text not null,
    duration_minutes integer not null,
    total_score integer not null
);

create table if not exists questions (
    id integer primary key autoincrement,
    paper_id integer not null references papers(id),
    question_type text not null,
    order_no integer not null,
    stem text not null,
    correct_answer text,
    reference_answer text,
    keywords text,
    score integer not null
);

create table if not exists question_options (
    id integer primary key autoincrement,
    question_id integer not null references questions(id),
    option_key text not null,
    option_text text not null
);

create table if not exists exam_attempts (
    id integer primary key autoincrement,
    user_id integer not null references users(id),
    paper_id integer not null references papers(id),
    status text not null check(status in ('in_progress', 'pending_review', 'completed')),
    objective_score real not null default 0,
    suggested_subjective_score real not null default 0,
    final_subjective_score real,
    final_score real,
    started_at text not null,
    submitted_at text
);

create table if not exists answers (
    id integer primary key autoincrement,
    attempt_id integer not null references exam_attempts(id),
    question_id integer not null references questions(id),
    answer_text text not null default '',
    auto_score real not null default 0,
    suggested_score real not null default 0,
    final_score real,
    unique(attempt_id, question_id)
);

create table if not exists subjective_reviews (
    id integer primary key autoincrement,
    answer_id integer not null references answers(id),
    reviewer_id integer not null references users(id),
    suggested_score real not null,
    final_score real not null,
    comment text,
    reviewed_at text not null
);

create table if not exists practice_attempts (
    id integer primary key autoincrement,
    user_id integer not null references users(id),
    question_id integer not null references questions(id),
    answer_text text not null,
    is_correct integer,
    created_at text not null
);
"""


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@contextmanager
def connect():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute(
            "select id from users where mobile = ?",
            (DEFAULT_ADMIN_MOBILE,),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                insert into users
                (name, mobile, password_hash, role, status, region, project, position, created_at)
                values (?, ?, ?, 'admin', 'approved', '', '', '管理员', ?)
                """,
                (
                    DEFAULT_ADMIN_NAME,
                    DEFAULT_ADMIN_MOBILE,
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    datetime.utcnow().isoformat(timespec="seconds"),
                ),
            )
```

- [ ] **Step 4: Run database test**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_services.py -v
```

Expected: PASS.

---

### Task 3: Word Paper Importer

**Files:**
- Create: `exam_system/docx_importer.py`
- Test: `tests/test_docx_importer.py`

- [ ] **Step 1: Write importer tests against the real document**

Create `tests/test_docx_importer.py`:

```python
from pathlib import Path

from exam_system.docx_importer import parse_docx


def test_parse_real_docx_extracts_five_papers():
    docx_files = list(Path.cwd().glob("*.docx"))
    assert docx_files

    papers = parse_docx(docx_files[0])

    assert len(papers) == 5
    assert papers[0]["title"].startswith("第一套")
    assert len(papers[0]["questions"]) == 38
    assert papers[0]["questions"][0]["question_type"] == "single_choice"
    assert papers[0]["questions"][0]["correct_answer"] == "B"
    assert papers[0]["questions"][16]["question_type"] == "multiple_choice"
    assert papers[0]["questions"][16]["correct_answer"] == "ABCDE"
    assert papers[0]["questions"][26]["question_type"] == "true_false"
    assert papers[0]["questions"][26]["correct_answer"] == "√"
    assert papers[0]["questions"][-1]["question_type"] == "case_analysis"
    assert papers[0]["questions"][-1]["score"] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_docx_importer.py -v
```

Expected: FAIL because importer is not implemented.

- [ ] **Step 3: Implement importer**

Create `exam_system/docx_importer.py`:

```python
import re
from pathlib import Path

from docx import Document


PAPER_RE = re.compile(r"^第[一二三四五]套")
ANSWER_RE = re.compile(r"(\d+)\.([A-E√×]+)")
OPTION_RE = re.compile(r"([A-E])\.([^A-E]+?)(?=\s+[A-E]\.|$)")


def _paragraphs(path: Path) -> list[str]:
    doc = Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def _split_papers(lines: list[str]) -> list[list[str]]:
    starts = [i for i, line in enumerate(lines) if PAPER_RE.match(line) and "参考答案" not in line]
    chunks = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        chunks.append(lines[start:end])
    return chunks


def _parse_answer_line(line: str) -> dict[int, str]:
    return {int(num): ans for num, ans in ANSWER_RE.findall(line.replace(" ", ""))}


def _options_from_text(text: str) -> list[dict[str, str]]:
    return [
        {"key": key, "text": value.strip()}
        for key, value in OPTION_RE.findall(text.replace("\n", " "))
    ]


def _stem_from_text(text: str) -> str:
    return re.split(r"\s+A\.", text.replace("\n", " "), maxsplit=1)[0].strip()


def _question_score(question_type: str) -> int:
    return {
        "single_choice": 2,
        "multiple_choice": 3,
        "true_false": 1,
        "short_answer": 7,
        "case_analysis": 15,
    }[question_type]


def _extract_keywords(reference_answer: str) -> str:
    terms = re.findall(r"[\u4e00-\u9fff]{2,}", reference_answer)
    seen = []
    for term in terms:
        if term not in seen and len(term) >= 2:
            seen.append(term)
        if len(seen) >= 12:
            break
    return ",".join(seen)


def _parse_paper(chunk: list[str]) -> dict:
    title = chunk[0]
    answer_index = next(i for i, line in enumerate(chunk) if line.endswith("参考答案"))
    question_lines = chunk[:answer_index]
    answer_lines = chunk[answer_index:]

    single_answers = _parse_answer_line(answer_lines[2])
    multi_answers = _parse_answer_line(answer_lines[4])
    judge_answers = _parse_answer_line(answer_lines[6])

    questions = []
    current_type = None
    type_counters = {
        "single_choice": 0,
        "multiple_choice": 0,
        "true_false": 0,
        "short_answer": 0,
        "case_analysis": 0,
    }

    for line in question_lines:
        if line.startswith("一、"):
            current_type = "single_choice"
            continue
        if line.startswith("二、"):
            current_type = "multiple_choice"
            continue
        if line.startswith("三、"):
            current_type = "true_false"
            continue
        if line.startswith("四、"):
            current_type = "short_answer"
            continue
        if line.startswith("五、"):
            current_type = "case_analysis"
            continue
        if current_type is None or line.startswith("考试时长") or line.startswith("命题依据"):
            continue

        if current_type in ("single_choice", "multiple_choice"):
            type_counters[current_type] += 1
            answer_map = single_answers if current_type == "single_choice" else multi_answers
            questions.append({
                "question_type": current_type,
                "order_no": len(questions) + 1,
                "type_order": type_counters[current_type],
                "stem": _stem_from_text(line),
                "options": _options_from_text(line),
                "correct_answer": answer_map[type_counters[current_type]],
                "reference_answer": "",
                "keywords": "",
                "score": _question_score(current_type),
            })
        elif current_type == "true_false":
            type_counters[current_type] += 1
            questions.append({
                "question_type": current_type,
                "order_no": len(questions) + 1,
                "type_order": type_counters[current_type],
                "stem": line,
                "options": [],
                "correct_answer": judge_answers[type_counters[current_type]],
                "reference_answer": "",
                "keywords": "",
                "score": _question_score(current_type),
            })
        elif current_type == "short_answer":
            type_counters[current_type] += 1
            ref_pos = 8 + type_counters[current_type] - 1
            reference = answer_lines[ref_pos].split(".", 1)[1] if "." in answer_lines[ref_pos] else answer_lines[ref_pos]
            questions.append({
                "question_type": current_type,
                "order_no": len(questions) + 1,
                "type_order": type_counters[current_type],
                "stem": line,
                "options": [],
                "correct_answer": "",
                "reference_answer": reference,
                "keywords": _extract_keywords(reference),
                "score": _question_score(current_type),
            })
        elif current_type == "case_analysis" and line.startswith("案例："):
            type_counters[current_type] += 1
            reference = "\n".join(answer_lines[-3:])
            questions.append({
                "question_type": current_type,
                "order_no": len(questions) + 1,
                "type_order": type_counters[current_type],
                "stem": "\n".join(question_lines[question_lines.index(line):answer_index]),
                "options": [],
                "correct_answer": "",
                "reference_answer": reference,
                "keywords": _extract_keywords(reference),
                "score": _question_score(current_type),
            })
            break

    return {
        "title": title,
        "duration_minutes": 50,
        "total_score": 100,
        "questions": questions,
    }


def parse_docx(path: Path) -> list[dict]:
    lines = _paragraphs(path)
    return [_parse_paper(chunk) for chunk in _split_papers(lines)]
```

- [ ] **Step 4: Run importer test**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_docx_importer.py -v
```

Expected: PASS.

---

### Task 4: Grading Engine

**Files:**
- Create: `exam_system/grading.py`
- Test: `tests/test_grading.py`

- [ ] **Step 1: Write grading tests**

Create `tests/test_grading.py`:

```python
from exam_system.grading import grade_objective, suggest_subjective_score


def test_single_choice_exact_match_scores_full_points():
    assert grade_objective("single_choice", "B", "B", 2) == 2
    assert grade_objective("single_choice", "A", "B", 2) == 0


def test_multiple_choice_requires_exact_set():
    assert grade_objective("multiple_choice", "ABCDE", "EDCBA", 3) == 3
    assert grade_objective("multiple_choice", "ABC", "ABCDE", 3) == 0
    assert grade_objective("multiple_choice", "ABCDE", "ABCD", 3) == 0


def test_true_false_scores_exact_symbol():
    assert grade_objective("true_false", "√", "√", 1) == 1
    assert grade_objective("true_false", "×", "√", 1) == 0


def test_subjective_suggestion_uses_keyword_ratio():
    score, hits = suggest_subjective_score("审批 库存 进场时间", "审批,库存,使用部位,进场时间", 7)
    assert score == 5.25
    assert hits == ["审批", "库存", "进场时间"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_grading.py -v
```

Expected: FAIL because grading module does not exist.

- [ ] **Step 3: Implement grading**

Create `exam_system/grading.py`:

```python
def _normalize_answer(value: str) -> str:
    return (value or "").strip().replace(" ", "").upper()


def grade_objective(question_type: str, candidate_answer: str, correct_answer: str, score: float) -> float:
    candidate = _normalize_answer(candidate_answer)
    correct = _normalize_answer(correct_answer)
    if question_type == "multiple_choice":
        return float(score) if set(candidate) == set(correct) and len(candidate) == len(correct) else 0.0
    return float(score) if candidate == correct else 0.0


def suggest_subjective_score(answer_text: str, keywords_csv: str, score: float) -> tuple[float, list[str]]:
    keywords = [item.strip() for item in (keywords_csv or "").split(",") if item.strip()]
    if not keywords:
        return 0.0, []
    hits = [keyword for keyword in keywords if keyword in answer_text]
    suggested = round(float(score) * len(hits) / len(keywords), 2)
    return suggested, hits
```

- [ ] **Step 4: Run grading tests**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_grading.py -v
```

Expected: PASS.

---

### Task 5: Service Layer

**Files:**
- Create: `exam_system/services.py`
- Modify: `tests/test_services.py`

- [ ] **Step 1: Extend service tests**

Replace `tests/test_services.py` with:

```python
import sqlite3

from exam_system import db, services


def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test.sqlite3"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(services, "DB_PATH", test_db)
    monkeypatch.setattr(services, "DATA_DIR", tmp_path)
    db.init_db()
    return test_db


def test_init_db_creates_default_admin(tmp_path, monkeypatch):
    test_db = setup_test_db(tmp_path, monkeypatch)
    with sqlite3.connect(test_db) as conn:
        row = conn.execute("select mobile, role, status from users where mobile = ?", ("admin",)).fetchone()
    assert row == ("admin", "admin", "approved")


def test_register_user_starts_pending_and_can_be_approved(tmp_path, monkeypatch):
    setup_test_db(tmp_path, monkeypatch)

    user_id = services.register_user("张三", "13800000000", "pw", "华东", "一项目", "物资管理员")
    pending = services.get_user_by_mobile("13800000000")
    assert pending["status"] == "pending"

    services.set_user_status(user_id, "approved")
    approved = services.get_user_by_mobile("13800000000")
    assert approved["status"] == "approved"


def test_seed_papers_and_submit_attempt(tmp_path, monkeypatch):
    setup_test_db(tmp_path, monkeypatch)
    papers = [{
        "title": "测试卷",
        "duration_minutes": 50,
        "total_score": 100,
        "questions": [
            {"question_type": "single_choice", "order_no": 1, "stem": "题1", "options": [{"key": "A", "text": "错"}, {"key": "B", "text": "对"}], "correct_answer": "B", "reference_answer": "", "keywords": "", "score": 2},
            {"question_type": "short_answer", "order_no": 2, "stem": "简答", "options": [], "correct_answer": "", "reference_answer": "审批 库存", "keywords": "审批,库存", "score": 7},
        ],
    }]
    services.seed_papers(papers)
    user_id = services.register_user("李四", "13900000000", "pw", "华东", "二项目", "仓管员")
    services.set_user_status(user_id, "approved")

    paper = services.list_papers()[0]
    questions = services.get_paper_questions(paper["id"])
    attempt_id = services.start_attempt(user_id, paper["id"])
    services.submit_attempt(attempt_id, {str(questions[0]["id"]): "B", str(questions[1]["id"]): "审批"})

    attempt = services.get_attempt(attempt_id)
    assert attempt["status"] == "pending_review"
    assert attempt["objective_score"] == 2
    assert attempt["suggested_subjective_score"] == 3.5
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_services.py -v
```

Expected: FAIL because service functions are missing.

- [ ] **Step 3: Implement services**

Create `exam_system/services.py` with functions for user registration, approval, paper seeding, attempt start, attempt submission, result lookup, subjective review, and CSV rows. Use `exam_system.db.connect`, `hash_password`, and `exam_system.grading`.

The service functions must use these exact names and return values:

- `register_user(name, mobile, password, region, project, position)` returns the new user id.
- `get_user_by_mobile(mobile)` returns a user dict or `None`.
- `get_user(user_id)` returns a user dict or `None`.
- `set_user_status(user_id, status)` updates the user status and returns `None`.
- `list_users(status=None, region=None, project=None, position=None, keyword=None)` returns a list of user dicts.
- `seed_papers(papers)` inserts imported paper data and returns `None`.
- `ensure_papers_seeded()` imports the root `.docx` when no papers exist and returns `None`.
- `list_papers()` returns a list of paper dicts.
- `get_paper_questions(paper_id)` returns questions with nested option lists.
- `start_attempt(user_id, paper_id)` returns the new attempt id.
- `submit_attempt(attempt_id, answers)` stores answers, grades them, updates the attempt, and returns `None`.
- `get_attempt(attempt_id)` returns an attempt dict.
- `list_user_attempts(user_id)` returns a list of attempt dicts.
- `list_pending_reviews()` returns subjective answers waiting for review.
- `review_answer(answer_id, reviewer_id, final_score, comment="")` stores a review and returns `None`.
- `list_results(filters)` returns filtered result dicts.

Implementation requirements:

- `register_user` inserts role `employee` and status `pending`.
- `seed_papers` clears existing paper/question rows before inserting imported papers.
- `ensure_papers_seeded` checks for existing papers, discovers the first `*.docx` in project root, parses it, and seeds it.
- `submit_attempt` grades objective answers with `grade_objective`, scores subjective answers with `suggest_subjective_score`, and sets attempt status to `pending_review` if subjective questions exist.
- `review_answer` writes `subjective_reviews`, updates `answers.final_score`, and completes the attempt when every subjective answer has a final score.

- [ ] **Step 4: Run service tests**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests\test_services.py -v
```

Expected: PASS.

---

### Task 6: Authentication And Employee Pages

**Files:**
- Create: `exam_system/auth.py`
- Modify: `app.py`
- Create templates: `base.html`, `login.html`, `register.html`, `pending.html`, `employee_home.html`, `practice.html`, `exam.html`, `results.html`
- Create: `static/styles.css`
- Create: `static/app.js`

- [ ] **Step 1: Implement auth helpers**

Create `exam_system/auth.py`:

```python
from functools import wraps

from flask import redirect, session, url_for

from .services import get_user


def current_user():
    user_id = session.get("user_id")
    return get_user(user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def approved_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["status"] != "approved":
            return redirect(url_for("pending"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] != "admin":
            return redirect(url_for("employee_home"))
        return view(*args, **kwargs)
    return wrapped
```

- [ ] **Step 2: Implement employee routes in `app.py`**

Replace the temporary `app.py` with routes for:

- `GET /login`, `POST /login`
- `GET /logout`
- `GET /register`, `POST /register`
- `GET /pending`
- `GET /home`
- `GET /practice/<paper_id>`
- `POST /practice/<paper_id>/answer`
- `GET /exam/<paper_id>`
- `POST /exam/<attempt_id>/submit`
- `GET /results`

Route requirements:

- Call `init_db()` and `ensure_papers_seeded()` in `create_app`.
- Login checks password with `hash_password`.
- Approved admins redirect to `/admin`.
- Approved employees redirect to `/home`.
- Pending and rejected users redirect to `/pending`.
- Exam submission reads form fields named `answer_<question_id>`.

- [ ] **Step 3: Create templates and responsive CSS**

Create templates with these visible sections:

- `base.html`: header, role-aware nav, flash messages, mobile-friendly main container.
- `login.html`: mobile and password fields, login button, registration link.
- `register.html`: all registration fields from the spec.
- `pending.html`: status message with rejection state.
- `employee_home.html`: paper cards and recent result summary.
- `practice.html`: questions, answer controls, immediate feedback after submit.
- `exam.html`: countdown timer, all questions, submit button.
- `results.html`: personal result cards/table.

Create `static/styles.css`:

- Max content width on desktop.
- Tables on desktop, cards on mobile.
- Bottom navigation under `720px`.
- Stable button sizes and large tap targets.

Create `static/app.js`:

- Countdown based on `data-deadline`.
- Auto-submit exam form when countdown reaches zero.
- Warn on page unload while exam form is dirty.

- [ ] **Step 4: Manual employee smoke test**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
```

Expected:

- `http://127.0.0.1:5000/login` opens.
- New employee can register.
- Pending employee cannot access `/home`.

---

### Task 7: Administrator Pages

**Files:**
- Modify: `app.py`
- Create templates: `admin_dashboard.html`, `admin_users.html`, `admin_papers.html`, `admin_review.html`, `admin_results.html`
- Modify: `static/styles.css`

- [ ] **Step 1: Add admin routes**

Add routes:

- `GET /admin`
- `GET /admin/users`
- `POST /admin/users/<user_id>/status`
- `GET /admin/papers`
- `GET /admin/review`
- `POST /admin/review/<answer_id>`
- `GET /admin/results`
- `GET /admin/results.csv`

Route requirements:

- Every route uses `@admin_required`.
- User status route accepts `approved` or `rejected`.
- Review route validates `final_score >= 0` and `final_score <= question.score`.
- CSV route returns UTF-8 with BOM so Excel opens Chinese text correctly.

- [ ] **Step 2: Add admin templates**

Create:

- `admin_dashboard.html`: metric cards for users, pending reviews, average score.
- `admin_users.html`: filters and approve/reject actions.
- `admin_papers.html`: paper list and read-only question details for first version.
- `admin_review.html`: candidate answer, reference answer, suggested score, editable final score.
- `admin_results.html`: filters, result list, CSV export link.

- [ ] **Step 3: Manual admin smoke test**

Run app, then:

- Login with `admin` / `admin123`.
- Approve a registered employee.
- Open paper list and confirm 5 papers exist.
- Submit an employee exam.
- Review subjective answers.
- Export CSV from admin results.

Expected: each step succeeds and data persists after restarting the Flask process.

---

### Task 8: End-To-End Verification And Mobile Layout Check

**Files:**
- Modify any app/template/style files needed to fix verification failures.

- [ ] **Step 1: Run automated tests**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run app locally**

Run:

```powershell
& "C:\Users\24525\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
```

Expected: Flask starts at `http://127.0.0.1:5000`.

- [ ] **Step 3: Verify full workflow**

Perform this workflow:

1. Register employee `测试员工 / 13800000000 / 123456 / 华东 / 测试项目 / 物资管理员`.
2. Login as admin.
3. Approve the employee.
4. Login as employee.
5. Open practice and answer at least one question.
6. Start an exam and submit answers.
7. Confirm objective score is calculated.
8. Login as admin.
9. Review subjective answers.
10. Confirm employee final score is visible.
11. Export results CSV.

Expected: workflow completes without server errors.

- [ ] **Step 4: Check responsive layout**

Use browser dev tools or Playwright at:

- Desktop: `1366x768`
- Mobile: `390x844`

Expected:

- No overlapping text.
- Forms fit screen width.
- Exam answer controls are tappable.
- Admin lists remain usable as cards or horizontally constrained tables.

- [ ] **Step 5: Update README with final status**

Add:

- Exact run command.
- Default admin credentials.
- Known first-version limits: no SMS, no SSO, no advanced proctoring.
- Location of SQLite database: `data/exam_system.sqlite3`.

---

## Self-Review

Spec coverage:

- Employee registration, approval, login, practice, exam, and results are covered in Tasks 5 and 6.
- Admin approval, papers, review, results, and CSV export are covered in Task 7.
- Word import is covered in Task 3.
- Objective and subjective grading are covered in Task 4.
- SQLite persistence is covered in Task 2 and Task 5.
- Responsive UI verification is covered in Task 8.

Placeholder scan:

- No task depends on unspecified files.
- No step uses deferred implementation wording.
- Current directory is not a git repository, so commit steps are intentionally omitted.

Type consistency:

- The service function names listed in Task 5 are the same functions used by later route tasks.
- Question type values match the design document.
- Attempt statuses match the schema and design document.
