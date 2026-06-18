from pathlib import Path

import pytest

from exam_system import docx_importer
from exam_system.docx_importer import parse_docx, parse_question_bank_docx


def test_root_docx_is_detected():
    docx_files = list(Path.cwd().glob("*.docx"))

    assert docx_files, "expected at least one .docx file in the project root"


def test_parse_current_root_docx_fails_on_incomplete_fifth_paper():
    root_docx = _original_exam_docx()

    with pytest.raises(ValueError) as exc_info:
        parse_docx(root_docx)

    message = str(exc_info.value)
    assert "paper 5" in message or "第五套" in message
    assert "reference answer section" in message or "参考答案" in message


def test_option_parser_supports_common_word_markers():
    options = docx_importer._parse_options("A.甲 B．乙 C、丙 D.丁 E．戊")

    assert options == [
        {"key": "A", "text": "甲"},
        {"key": "B", "text": "乙"},
        {"key": "C", "text": "丙"},
        {"key": "D", "text": "丁"},
        {"key": "E", "text": "戊"},
    ]


def test_validation_rejects_objective_question_with_empty_answer():
    questions = [
        {
            "question_type": "single_choice",
            "type_order": 1,
            "correct_answer": "",
            "reference_answer": "",
            "options": [
                {"key": "A", "text": "甲"},
                {"key": "B", "text": "乙"},
                {"key": "C", "text": "丙"},
                {"key": "D", "text": "丁"},
            ],
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert "single_choice" in message
    assert "type_order 1" in message
    assert "correct_answer" in message


@pytest.mark.parametrize(
    "options",
    [
        [
            {"key": "A", "text": "甲"},
            {"key": "B", "text": "乙"},
            {"key": "C", "text": "丙"},
            {"key": "D", "text": "丁"},
        ],
        [
            {"key": "A", "text": "甲"},
            {"key": "B", "text": ""},
            {"key": "C", "text": "丙"},
            {"key": "D", "text": "丁"},
            {"key": "E", "text": "戊"},
        ],
    ],
)
def test_validation_rejects_choice_question_with_missing_or_empty_options(options):
    questions = [
        {
            "question_type": "multiple_choice",
            "type_order": 1,
            "correct_answer": "ABCDE",
            "reference_answer": "",
            "options": options,
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert "multiple_choice" in message
    assert "type_order 1" in message
    assert "options" in message


def test_validation_rejects_invalid_single_choice_answer_shape():
    questions = [
        {
            "question_type": "single_choice",
            "type_order": 1,
            "correct_answer": "AB",
            "reference_answer": "",
            "options": [
                {"key": "A", "text": "甲"},
                {"key": "B", "text": "乙"},
                {"key": "C", "text": "丙"},
                {"key": "D", "text": "丁"},
            ],
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert "single_choice" in message
    assert "type_order 1" in message
    assert "correct_answer" in message


def test_validation_rejects_invalid_true_false_answer():
    questions = [
        {
            "question_type": "true_false",
            "type_order": 1,
            "correct_answer": "A",
            "reference_answer": "",
            "options": [],
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert "true_false" in message
    assert "type_order 1" in message
    assert "correct_answer" in message


@pytest.mark.parametrize(
    "question_type,correct_answer,options",
    [
        (
            "single_choice",
            "A",
            [
                {"key": "A", "text": "甲"},
                {"key": "C", "text": "丙"},
                {"key": "B", "text": "乙"},
                {"key": "D", "text": "丁"},
            ],
        ),
        (
            "multiple_choice",
            "ABCDE",
            [
                {"key": "A", "text": "甲"},
                {"key": "B", "text": "乙"},
                {"key": "C", "text": "丙"},
                {"key": "D", "text": "丁"},
                {"key": "D", "text": "重复"},
            ],
        ),
    ],
)
def test_validation_rejects_duplicate_or_misordered_option_keys(
    question_type, correct_answer, options
):
    questions = [
        {
            "question_type": question_type,
            "type_order": 1,
            "correct_answer": correct_answer,
            "reference_answer": "",
            "options": options,
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert question_type in message
    assert "type_order 1" in message
    assert "option keys" in message


def test_validation_rejects_missing_subjective_reference_answer():
    questions = [
        {
            "question_type": "short_answer",
            "type_order": 1,
            "correct_answer": "",
            "reference_answer": "",
            "options": [],
        }
    ]

    with pytest.raises(ValueError) as exc_info:
        docx_importer._validate_questions(questions, 1, "第一套")

    message = str(exc_info.value)
    assert "paper 1" in message
    assert "short_answer" in message
    assert "type_order 1" in message
    assert "reference_answer" in message


def test_complete_current_docx_chunks_one_to_four_parse_with_expected_counts():
    root_docx = _original_exam_docx()
    lines = docx_importer._read_lines(root_docx)
    paper_ranges = docx_importer._paper_ranges(lines)

    papers = []
    for paper_number, start_index in enumerate(paper_ranges[:4], start=1):
        end_index = paper_ranges[paper_number]
        papers.append(docx_importer._parse_paper(lines[start_index:end_index], paper_number))

    for paper in papers:
        counts = {}
        for question in paper["questions"]:
            counts[question["question_type"]] = counts.get(question["question_type"], 0) + 1

        assert len(paper["questions"]) == 38
        assert counts == {
            "single_choice": 16,
            "multiple_choice": 10,
            "true_false": 9,
            "short_answer": 2,
            "case_analysis": 1,
        }


def test_parse_project_material_question_bank_docx():
    bank_docx = next(path for path in Path.cwd().glob("*.docx") if path.stat().st_size == 23013)

    paper = parse_question_bank_docx(bank_docx)
    counts = {}
    for question in paper["questions"]:
        counts[question["question_type"]] = counts.get(question["question_type"], 0) + 1

    assert paper["title"] == "项目物资管理岗位考核题库"
    assert paper["total_score"] == 150
    assert len(paper["questions"]) == 80
    assert counts == {
        "single_choice": 30,
        "multiple_choice": 20,
        "true_false": 30,
    }
    assert paper["questions"][0]["correct_answer"] == "B"
    assert paper["questions"][30]["correct_answer"] == "ABCD"
    assert paper["questions"][50]["correct_answer"] == "×"
    assert paper["questions"][51]["correct_answer"] == "√"


def _original_exam_docx():
    return next(path for path in Path.cwd().glob("*.docx") if path.stat().st_size == 40539)
