"""Scoring helpers for objective and subjective exam answers."""


def _normalize_answer(value: str) -> str:
    return (value or "").strip().replace(" ", "").upper()


def grade_objective(
    question_type: str,
    candidate_answer: str,
    correct_answer: str,
    score: float,
) -> float:
    candidate = _normalize_answer(candidate_answer)
    correct = _normalize_answer(correct_answer)

    if question_type == "multiple_choice":
        return float(score) if set(candidate) == set(correct) and len(candidate) == len(correct) else 0.0

    return float(score) if candidate == correct else 0.0


def suggest_subjective_score(
    answer_text: str,
    keywords_csv: str,
    score: float,
) -> tuple[float, list[str]]:
    keywords = [item.strip() for item in (keywords_csv or "").split(",") if item.strip()]
    if not keywords:
        return 0.0, []

    hits = [keyword for keyword in keywords if keyword in answer_text]
    suggested = round(float(score) * len(hits) / len(keywords), 2)
    return suggested, hits
