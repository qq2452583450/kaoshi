"""Import exam papers and reference answers from Word documents."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from exam_system.config import EXAM_DURATION_MINUTES, QUESTION_SCORES


PAPER_TITLE_RE = re.compile(r"^第[一二三四五]套(?!.*参考答案)")
ANSWER_TOKEN_RE = re.compile(r"(\d+)\s*[.．、]\s*([A-E√×]+)")
NUMBERED_TEXT_RE = re.compile(r"^(\d+)\s*[.．、]\s*(.*)")
OPTION_RE = re.compile(r"([A-E])[.．、](.*?)(?=\s+[A-E][.．、]|$)")


def parse_docx(path: Path) -> list[dict]:
    """Parse five exam papers from a Word document."""
    lines = _read_lines(path)
    paper_ranges = _paper_ranges(lines)
    papers = []

    for paper_number, start_index in enumerate(paper_ranges, start=1):
        end_index = paper_ranges[paper_number] if paper_number < len(paper_ranges) else len(lines)
        paper_lines = lines[start_index:end_index]
        papers.append(_parse_paper(paper_lines, paper_number))

    return papers


def parse_available_docx(path: Path) -> tuple[list[dict], str]:
    """Parse complete leading papers and return a warning for the first malformed chunk."""
    lines = _read_lines(path)
    paper_ranges = _paper_ranges(lines)
    papers = []

    for paper_number, start_index in enumerate(paper_ranges, start=1):
        end_index = paper_ranges[paper_number] if paper_number < len(paper_ranges) else len(lines)
        paper_lines = lines[start_index:end_index]
        try:
            papers.append(_parse_paper(paper_lines, paper_number))
        except ValueError as exc:
            if not papers:
                raise
            return papers, str(exc)

    return papers, ""


def _read_lines(path: Path) -> list[str]:
    doc = Document(path)
    lines: list[str] = []
    for paragraph in doc.paragraphs:
        for line in paragraph.text.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(stripped)
    return lines


def _paper_ranges(lines: list[str]) -> list[int]:
    ranges = [
        index
        for index, line in enumerate(lines)
        if PAPER_TITLE_RE.match(line) and "参考答案" not in line
    ]
    if len(ranges) != 5:
        raise ValueError(f"Expected 5 paper chunks, found {len(ranges)}.")
    return ranges


def _parse_paper(lines: list[str], paper_number: int) -> dict:
    paper_title = lines[0] if lines else f"paper {paper_number}"
    answer_start = _find_index(
        lines,
        lambda line: "参考答案" in line,
        (
            f"Could not find reference answer section for paper "
            f"{paper_number} ({paper_title})."
        ),
    )
    question_lines = lines[:answer_start]
    answer_lines = lines[answer_start:]

    section_indexes = _question_section_indexes(question_lines, paper_number)
    answer_indexes = _answer_section_indexes(answer_lines, paper_number)
    answers = _parse_answers(answer_lines, answer_indexes)

    questions: list[dict] = []
    order_no = 1

    single_questions = _parse_choice_questions(
        question_lines[section_indexes["single"] + 1 : section_indexes["multiple"]],
        "single_choice",
        answers["single"],
    )
    questions.extend(_with_order_numbers(single_questions, order_no))
    order_no += len(single_questions)

    multiple_questions = _parse_choice_questions(
        question_lines[section_indexes["multiple"] + 1 : section_indexes["true_false"]],
        "multiple_choice",
        answers["multiple"],
    )
    questions.extend(_with_order_numbers(multiple_questions, order_no))
    order_no += len(multiple_questions)

    true_false_questions = _parse_true_false_questions(
        question_lines[section_indexes["true_false"] + 1 : section_indexes["short_answer"]],
        answers["true_false"],
    )
    questions.extend(_with_order_numbers(true_false_questions, order_no))
    order_no += len(true_false_questions)

    short_answer_questions = _parse_subjective_questions(
        question_lines[section_indexes["short_answer"] + 1 : section_indexes["case_analysis"]],
        "short_answer",
        answers["short_answer"],
    )
    questions.extend(_with_order_numbers(short_answer_questions, order_no))
    order_no += len(short_answer_questions)

    case_questions = _parse_subjective_questions(
        question_lines[section_indexes["case_analysis"] + 1 :],
        "case_analysis",
        {1: "\n".join(answers["case_analysis"].values())},
    )
    questions.extend(_with_order_numbers(case_questions, order_no))

    if len(questions) != 38:
        _raise_validation_error(
            paper_number,
            paper_title,
            "all_questions",
            "n/a",
            f"expected 38 questions, found {len(questions)}",
        )
    _validate_questions(questions, paper_number, paper_title)

    return {
        "title": paper_title,
        "total_score": 100,
        "duration_minutes": EXAM_DURATION_MINUTES,
        "questions": questions,
    }


def _question_section_indexes(lines: list[str], paper_number: int) -> dict[str, int]:
    return {
        "single": _find_index(
            lines, lambda line: "单项选择题" in line, f"Paper {paper_number} missing single-choice section."
        ),
        "multiple": _find_index(
            lines, lambda line: "多项选择题" in line, f"Paper {paper_number} missing multiple-choice section."
        ),
        "true_false": _find_index(
            lines, lambda line: "判断题" in line, f"Paper {paper_number} missing true/false section."
        ),
        "short_answer": _find_index(
            lines, lambda line: "简答题" in line, f"Paper {paper_number} missing short-answer section."
        ),
        "case_analysis": _find_index(
            lines, lambda line: "案例分析题" in line, f"Paper {paper_number} missing case-analysis section."
        ),
    }


def _answer_section_indexes(lines: list[str], paper_number: int) -> dict[str, int]:
    return {
        "single": _find_index(
            lines, lambda line: "单项选择题" in line, f"Paper {paper_number} missing single-choice answers."
        ),
        "multiple": _find_index(
            lines, lambda line: "多项选择题" in line, f"Paper {paper_number} missing multiple-choice answers."
        ),
        "true_false": _find_index(
            lines, lambda line: "判断题" in line, f"Paper {paper_number} missing true/false answers."
        ),
        "short_answer": _find_index(
            lines, lambda line: "简答题" in line, f"Paper {paper_number} missing short-answer references."
        ),
        "case_analysis": _find_index(
            lines, lambda line: "案例分析题" in line, f"Paper {paper_number} missing case-analysis references."
        ),
    }


def _parse_answers(lines: list[str], indexes: dict[str, int]) -> dict[str, dict[int, str]]:
    return {
        "single": _parse_answer_tokens(lines[indexes["single"] + 1 : indexes["multiple"]]),
        "multiple": _parse_answer_tokens(lines[indexes["multiple"] + 1 : indexes["true_false"]]),
        "true_false": _parse_answer_tokens(lines[indexes["true_false"] + 1 : indexes["short_answer"]]),
        "short_answer": _parse_numbered_blocks(
            lines[indexes["short_answer"] + 1 : indexes["case_analysis"]]
        ),
        "case_analysis": _parse_numbered_blocks(lines[indexes["case_analysis"] + 1 :]),
    }


def _parse_answer_tokens(lines: list[str]) -> dict[int, str]:
    answers: dict[int, str] = {}
    for line in lines:
        for number, answer in ANSWER_TOKEN_RE.findall(line):
            answers[int(number)] = answer
    return answers


def _parse_numbered_blocks(lines: list[str]) -> dict[int, str]:
    blocks: dict[int, list[str]] = {}
    current_number: int | None = None

    for line in lines:
        match = NUMBERED_TEXT_RE.match(line)
        if match:
            current_number = int(match.group(1))
            blocks[current_number] = [match.group(2).strip()]
        elif current_number is not None:
            blocks[current_number].append(line)

    return {
        number: "\n".join(part for part in parts if part).strip()
        for number, parts in blocks.items()
    }


def _parse_choice_questions(
    lines: list[str], question_type: str, answers: dict[int, str]
) -> list[dict]:
    questions: list[dict] = []
    stem_parts: list[str] = []

    for _, line in enumerate(lines):
        options = _parse_options(line)
        if not options:
            stem_parts.append(line)
            continue

        option_match = OPTION_RE.search(line)
        if option_match is None:
            raise ValueError(f"Could not locate options while parsing {question_type}: {line}")
        option_start = option_match.start()
        inline_stem = line[:option_start].strip()
        if inline_stem:
            stem_parts.append(inline_stem)

        type_order = len(questions) + 1
        questions.append(
            _question(
                question_type=question_type,
                type_order=type_order,
                stem="\n".join(stem_parts).strip(),
                options=options,
                correct_answer=answers.get(type_order, ""),
            )
        )
        stem_parts = []

    if stem_parts:
        raise ValueError(f"Unmatched stem while parsing {question_type}: {stem_parts[-1]}")

    return questions


def _parse_options(line: str) -> list[dict]:
    return [
        {"key": match.group(1), "text": match.group(2).strip()}
        for match in OPTION_RE.finditer(line)
    ]


def _validate_questions(questions: list[dict], paper_number: int, paper_title: str) -> None:
    expected_counts = {
        "single_choice": 16,
        "multiple_choice": 10,
        "true_false": 9,
        "short_answer": 2,
        "case_analysis": 1,
    }
    objective_types = {"single_choice", "multiple_choice", "true_false"}
    subjective_types = {"short_answer", "case_analysis"}

    for question in questions:
        question_type = question["question_type"]
        type_order = question["type_order"]

        if question_type in objective_types and not question.get("correct_answer"):
            _raise_validation_error(
                paper_number,
                paper_title,
                question_type,
                type_order,
                "missing correct_answer",
            )

        if question_type in subjective_types and not question.get("reference_answer"):
            _raise_validation_error(
                paper_number,
                paper_title,
                question_type,
                type_order,
                "missing reference_answer",
            )

        expected_option_count = {
            "single_choice": 4,
            "multiple_choice": 5,
        }.get(question_type)
        if expected_option_count is not None:
            options = question.get("options", [])
            option_keys = [option.get("key") for option in options]
            expected_option_keys = (
                ["A", "B", "C", "D"]
                if question_type == "single_choice"
                else ["A", "B", "C", "D", "E"]
            )
            if len(options) != expected_option_count:
                _raise_validation_error(
                    paper_number,
                    paper_title,
                    question_type,
                    type_order,
                    f"expected {expected_option_count} options, found {len(options)}",
                )
            for option in options:
                if not option.get("text"):
                    _raise_validation_error(
                        paper_number,
                        paper_title,
                        question_type,
                        type_order,
                        f"options: option {option.get('key', '')} has empty text",
                    )

            if option_keys != expected_option_keys:
                _raise_validation_error(
                    paper_number,
                    paper_title,
                    question_type,
                    type_order,
                    f"option keys must be {expected_option_keys}, found {option_keys}",
                )

            correct_answer = question.get("correct_answer", "")
            if question_type == "single_choice":
                if len(correct_answer) != 1 or correct_answer not in option_keys:
                    _raise_validation_error(
                        paper_number,
                        paper_title,
                        question_type,
                        type_order,
                        f"invalid correct_answer {correct_answer!r}",
                    )
            else:
                answer_letters = list(correct_answer)
                if (
                    any(letter not in option_keys for letter in answer_letters)
                    or len(set(answer_letters)) != len(answer_letters)
                ):
                    _raise_validation_error(
                        paper_number,
                        paper_title,
                        question_type,
                        type_order,
                        f"invalid correct_answer {correct_answer!r}",
                    )

        if question_type == "true_false" and question.get("correct_answer") not in {"√", "×"}:
            _raise_validation_error(
                paper_number,
                paper_title,
                question_type,
                type_order,
                f"invalid correct_answer {question.get('correct_answer')!r}",
            )

    actual_counts = {
        question_type: sum(1 for question in questions if question["question_type"] == question_type)
        for question_type in expected_counts
    }
    for question_type, expected_count in expected_counts.items():
        actual_count = actual_counts[question_type]
        if actual_count != expected_count:
            _raise_validation_error(
                paper_number,
                paper_title,
                question_type,
                "n/a",
                f"expected {expected_count} questions, found {actual_count}",
            )


def _raise_validation_error(
    paper_number: int,
    paper_title: str,
    question_type: str,
    type_order: int | str,
    detail: str,
) -> None:
    raise ValueError(
        f"paper {paper_number} ({paper_title}) {question_type} "
        f"type_order {type_order}: {detail}."
    )


def _parse_true_false_questions(lines: list[str], answers: dict[int, str]) -> list[dict]:
    return [
        _question(
            question_type="true_false",
            type_order=index + 1,
            stem=line,
            options=[],
            correct_answer=answers.get(index + 1, ""),
        )
        for index, line in enumerate(lines)
    ]


def _parse_subjective_questions(
    lines: list[str], question_type: str, reference_answers: dict[int, str]
) -> list[dict]:
    if question_type == "case_analysis":
        stem = "\n".join(lines).strip()
        reference_answer = reference_answers.get(1, "")
        return [
            _question(
                question_type=question_type,
                type_order=1,
                stem=stem,
                options=[],
                correct_answer="",
                reference_answer=reference_answer,
                keywords=_keywords(reference_answer or stem),
            )
        ]

    questions = []
    for index, line in enumerate(lines):
        reference_answer = reference_answers.get(index + 1, "")
        questions.append(
            _question(
                question_type=question_type,
                type_order=index + 1,
                stem=line,
                options=[],
                correct_answer="",
                reference_answer=reference_answer,
                keywords=_keywords(reference_answer or line),
            )
        )
    return questions


def _question(
    *,
    question_type: str,
    type_order: int,
    stem: str,
    options: list[dict],
    correct_answer: str,
    reference_answer: str = "",
    keywords: str = "",
) -> dict:
    return {
        "question_type": question_type,
        "order_no": 0,
        "type_order": type_order,
        "stem": stem,
        "options": options,
        "correct_answer": correct_answer,
        "reference_answer": reference_answer,
        "keywords": keywords,
        "score": QUESTION_SCORES[question_type],
    }


def _with_order_numbers(questions: list[dict], start: int) -> list[dict]:
    for offset, question in enumerate(questions):
        question["order_no"] = start + offset
    return questions


def _keywords(text: str) -> str:
    phrases = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    keywords: list[str] = []
    for phrase in phrases:
        for term in re.split(r"[，。；、：；（）()]", phrase):
            term = term.strip()
            if 2 <= len(term) <= 12 and term not in keywords:
                keywords.append(term)
            if len(keywords) >= 12:
                return ",".join(keywords)
    return ",".join(keywords or phrases[:1])


def _find_index(lines: list[str], predicate, error_message: str) -> int:
    for index, line in enumerate(lines):
        if predicate(line):
            return index
    raise ValueError(error_message)
