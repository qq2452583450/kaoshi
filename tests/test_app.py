from werkzeug.datastructures import MultiDict

from app import _collect_answers, create_app
from exam_system import db, services


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.sqlite3")
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return app.test_client()


def test_registration_login_pending_and_admin_approval_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/register",
        data={
            "name": "测试用户",
            "mobile": "13600000000",
            "password": "123456",
            "region": "华东区域",
            "project": "测试项目部",
            "position": "物资管理员",
        },
        follow_redirects=True,
    )
    assert "等待管理员审核" in response.get_data(as_text=True)

    client.get("/logout")
    response = client.post(
        "/login",
        data={"mobile": "13600000000", "password": "123456"},
        follow_redirects=True,
    )
    assert "等待管理员审核" in response.get_data(as_text=True)

    client.get("/logout")
    response = client.post(
        "/login",
        data={"mobile": "admin", "password": "admin123"},
        follow_redirects=True,
    )
    assert "管理看板" in response.get_data(as_text=True)

    response = client.get("/admin/users")
    html = response.get_data(as_text=True)
    assert "测试用户" in html

    client.post("/admin/users/2/status", data={"status": "approved"}, follow_redirects=True)
    client.get("/logout")
    response = client.post(
        "/login",
        data={"mobile": "13600000000", "password": "123456"},
        follow_redirects=True,
    )

    assert "学习首页" in response.get_data(as_text=True)


def test_collect_answers_preserves_multiple_choice_values():
    form = MultiDict(
        [
            ("answer_1", "A"),
            ("answer_1", "C"),
            ("answer_2", "√"),
        ]
    )
    questions = [{"id": 1}, {"id": 2}, {"id": 3}]

    assert _collect_answers(form, questions) == {"1": "AC", "2": "√", "3": ""}


def test_admin_selected_paper_controls_employee_exam_access(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    user_id = services.register_user(
        "指定考试用户",
        "13400000000",
        "123456",
        "华东区域",
        "测试项目部",
        "物资管理员",
    )
    services.set_user_status(user_id, "approved")
    papers = services.list_papers()
    first_paper, second_paper = papers[0], papers[1]

    client.post("/login", data={"mobile": "admin", "password": "admin123"}, follow_redirects=True)
    response = client.post(
        "/admin/papers/current",
        data={"paper_id": str(second_paper["id"])},
        follow_redirects=True,
    )
    assert "当前考试试卷已更新" in response.get_data(as_text=True)

    client.get("/logout")
    response = client.post(
        "/login",
        data={"mobile": "13400000000", "password": "123456"},
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)
    assert second_paper["title"] in html
    assert f'/exam/{second_paper["id"]}' in html
    assert f'/exam/{first_paper["id"]}' not in html

    response = client.get(f"/exam/{first_paper['id']}", follow_redirects=True)
    html = response.get_data(as_text=True)
    assert "管理员当前指定的考试试卷为" in html
    assert second_paper["title"] in html

    response = client.get(f"/exam/{second_paper['id']}")
    assert "正式考试" in response.get_data(as_text=True)


def test_exam_submission_admin_review_and_results_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    user_id = services.register_user(
        "考试用户",
        "13500000000",
        "123456",
        "华东区域",
        "测试项目部",
        "物资管理员",
    )
    services.set_user_status(user_id, "approved")
    paper = services.list_papers()[0]

    client.post(
        "/login",
        data={"mobile": "13500000000", "password": "123456"},
        follow_redirects=True,
    )
    response = client.get(f"/exam/{paper['id']}")
    assert "正式考试" in response.get_data(as_text=True)
    attempt_id = services.list_user_attempts(user_id)[0]["id"]
    questions = services.get_paper_questions(paper["id"])
    data = {f"answer_{question['id']}": question["correct_answer"] for question in questions if question["correct_answer"]}
    for question in questions:
        if not question["correct_answer"]:
            data[f"answer_{question['id']}"] = "审批 库存 平台 台账"

    response = client.post(f"/exam/{attempt_id}/submit", data=data, follow_redirects=True)
    assert "我的成绩" in response.get_data(as_text=True)
    assert services.get_attempt(attempt_id)["status"] == "pending_review"

    client.get("/logout")
    client.post("/login", data={"mobile": "admin", "password": "admin123"}, follow_redirects=True)
    pending = services.list_pending_reviews()
    assert pending
    for item in pending:
        client.post(
            f"/admin/review/{item['answer_id']}",
            data={"final_score": "1", "comment": "ok"},
            follow_redirects=True,
        )

    response = client.get("/admin/results")
    html = response.get_data(as_text=True)
    assert "考试用户" in html
    assert services.get_attempt(attempt_id)["status"] == "completed"
