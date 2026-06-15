"""Configuration constants for the local exam system."""

import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "exam_system.sqlite3"

SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

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
