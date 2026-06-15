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
    score, hits = suggest_subjective_score(
        "审批 库存 进场时间",
        "审批,库存,使用部位,进场时间",
        7,
    )

    assert score == 5.25
    assert hits == ["审批", "库存", "进场时间"]
