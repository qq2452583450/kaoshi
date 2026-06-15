"""SQLite persistence helpers for the local exam system."""

import hashlib
import os
import datetime
import sqlite3
from contextlib import contextmanager

from exam_system.config import (
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
    password_salt blob not null,
    role text not null check (role in ('employee', 'admin')),
    status text not null check (status in ('pending', 'approved', 'rejected')),
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

create table if not exists app_settings (
    key text primary key,
    value text not null
);

create table if not exists questions (
    id integer primary key autoincrement,
    paper_id integer not null,
    question_type text not null,
    order_no integer not null,
    stem text not null,
    correct_answer text,
    reference_answer text,
    keywords text,
    score integer not null,
    foreign key (paper_id) references papers (id)
);

create table if not exists question_options (
    id integer primary key autoincrement,
    question_id integer not null,
    option_key text not null,
    option_text text not null,
    foreign key (question_id) references questions (id)
);

create table if not exists exam_attempts (
    id integer primary key autoincrement,
    user_id integer not null,
    paper_id integer not null,
    status text not null check (
        status in ('in_progress', 'pending_review', 'completed')
    ),
    objective_score real not null default 0,
    suggested_subjective_score real not null default 0,
    final_subjective_score real,
    final_score real,
    started_at text not null,
    submitted_at text,
    foreign key (user_id) references users (id),
    foreign key (paper_id) references papers (id)
);

create table if not exists answers (
    id integer primary key autoincrement,
    attempt_id integer not null,
    question_id integer not null,
    answer_text text not null default '',
    auto_score real not null default 0,
    suggested_score real not null default 0,
    final_score real,
    unique (attempt_id, question_id),
    foreign key (attempt_id) references exam_attempts (id),
    foreign key (question_id) references questions (id)
);

create table if not exists subjective_reviews (
    id integer primary key autoincrement,
    answer_id integer not null,
    reviewer_id integer not null,
    suggested_score real not null,
    final_score real not null,
    comment text,
    reviewed_at text not null,
    foreign key (answer_id) references answers (id),
    foreign key (reviewer_id) references users (id)
);

create table if not exists practice_attempts (
    id integer primary key autoincrement,
    user_id integer not null,
    question_id integer not null,
    answer_text text not null,
    is_correct integer,
    created_at text not null,
    foreign key (user_id) references users (id),
    foreign key (question_id) references questions (id)
);
"""


def hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
    """Hash password with PBKDF2 and return (hash_hex, salt)."""
    if salt is None:
        salt = os.urandom(32)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=100000,
    )
    return hash_bytes.hex(), salt


def verify_password(password: str, stored_hash: str, salt: bytes) -> bool:
    """Verify password against stored hash and salt."""
    hash_hex, _ = hash_password(password, salt)
    return hash_hex == stored_hash


@contextmanager
def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("pragma foreign_keys = on")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)
        password_hash, password_salt = hash_password(DEFAULT_ADMIN_PASSWORD)
        conn.execute(
            """
            insert into users (
                name,
                mobile,
                password_hash,
                password_salt,
                role,
                status,
                position,
                created_at
            )
            select ?, ?, ?, ?, 'admin', 'approved', 'admin', ?
            where not exists (
                select 1 from users where mobile = ?
            )
            """,
            (
                DEFAULT_ADMIN_NAME,
                DEFAULT_ADMIN_MOBILE,
                password_hash,
                password_salt,
                datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                DEFAULT_ADMIN_MOBILE,
            ),
        )
