"""Flask application entry point for the local exam system."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from exam_system.auth import admin_required, approved_required, current_user, login_required, csrf_required, generate_csrf_token
from exam_system.config import EXAM_DURATION_MINUTES, SECRET_KEY
from exam_system.db import hash_password, init_db, verify_password
from exam_system import services


def _collect_answers(form, questions) -> dict[str, str]:
    answers = {}
    for question in questions:
        key = f"answer_{question['id']}"
        values = form.getlist(key)
        answers[str(question["id"])] = "".join(values) if values else ""
    return answers


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    init_db()
    app.config["IMPORT_STATUS"] = services.ensure_papers_seeded()

    @app.context_processor
    def inject_user():
        status_labels = {
            "pending": "待审核",
            "approved": "已通过",
            "rejected": "已驳回",
            "in_progress": "考试中",
            "pending_review": "待阅卷",
            "completed": "已完成",
        }
        question_type_labels = {
            "single_choice": "单选题",
            "multiple_choice": "多选题",
            "true_false": "判断题",
            "short_answer": "简答题",
            "case_analysis": "案例分析题",
        }
        return {
            "current_user": current_user(),
            "csrf_token": generate_csrf_token,
            "status_label": lambda value: status_labels.get(value, value),
            "question_type_label": lambda value: question_type_labels.get(value, value),
        }

    @app.get("/")
    def index():
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        if user["status"] != "approved":
            return redirect(url_for("pending"))
        return redirect(url_for("employee_home"))

    @app.route("/login", methods=["GET", "POST"])
    @csrf_required
    def login():
        if request.method == "POST":
            user = services.get_user_by_mobile(request.form.get("mobile", "").strip())
            if not user or not verify_password(
                request.form.get("password", ""),
                user["password_hash"],
                user["password_salt"],
            ):
                flash("账号或密码不正确。")
                return render_template("login.html", title="登录")
            session["user_id"] = user["id"]
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            if user["status"] != "approved":
                return redirect(url_for("pending"))
            return redirect(url_for("employee_home"))
        return render_template("login.html", title="登录")

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    @csrf_required
    def register():
        if request.method == "POST":
            try:
                user_id = services.register_user(
                    request.form["name"],
                    request.form["mobile"],
                    request.form["password"],
                    request.form["region"],
                    request.form["project"],
                    request.form["position"],
                )
            except Exception as exc:  # sqlite duplicate errors are shown plainly in local demo.
                flash(f"注册失败：{exc}")
                return render_template("register.html", title="注册")
            session["user_id"] = user_id
            return redirect(url_for("pending"))
        return render_template("register.html", title="注册")

    @app.get("/pending")
    @login_required
    def pending():
        return render_template("pending.html", title="等待审核")

    @app.get("/home")
    @approved_required
    def employee_home():
        user = current_user()
        return render_template(
            "employee_home.html",
            title="首页",
            papers=services.list_papers(),
            current_exam_paper=services.get_current_exam_paper(),
            attempts=services.list_user_attempts(user["id"]),
            import_status=app.config.get("IMPORT_STATUS", {}),
        )

    @app.route("/practice/random", methods=["GET", "POST"])
    @approved_required
    @csrf_required
    def random_practice():
        feedback = None
        if request.method == "POST":
            question_ids = request.form.getlist("question_ids")
            questions = services.get_questions_by_ids(question_ids)
            feedback = _collect_answers(request.form, questions)
        else:
            questions = services.get_random_practice_questions()
        return render_template("practice.html", title="随机练习", questions=questions, feedback=feedback)

    @app.route("/practice/<int:paper_id>", methods=["GET", "POST"])
    @approved_required
    @csrf_required
    def practice(paper_id):
        questions = services.get_paper_questions(paper_id)
        feedback = None
        if request.method == "POST":
            feedback = _collect_answers(request.form, questions)
        return render_template("practice.html", title="试卷练习", questions=questions, feedback=feedback)

    @app.get("/exam/<int:paper_id>")
    @approved_required
    def exam(paper_id):
        current_paper = services.get_current_exam_paper()
        if current_paper and paper_id != current_paper["id"]:
            flash(f"管理员当前指定的考试试卷为：{current_paper['title']}。")
            return redirect(url_for("employee_home"))
        user = current_user()
        attempt_id = services.start_attempt(user["id"], paper_id)
        deadline = datetime.now(timezone.utc) + timedelta(minutes=EXAM_DURATION_MINUTES)
        return render_template(
            "exam.html",
            title="正式考试",
            attempt_id=attempt_id,
            questions=services.get_paper_questions(paper_id),
            deadline=deadline.isoformat(),
        )

    @app.post("/exam/<int:attempt_id>/submit")
    @approved_required
    @csrf_required
    def submit_exam(attempt_id):
        attempt = services.get_attempt(attempt_id)
        answers = _collect_answers(request.form, services.get_paper_questions(attempt["paper_id"]))
        services.submit_attempt(attempt_id, answers)
        flash("已交卷，简答题和案例题等待管理员阅卷。")
        return redirect(url_for("results"))

    @app.get("/results")
    @approved_required
    def results():
        user = current_user()
        return render_template("results.html", title="我的成绩", attempts=services.list_user_attempts(user["id"]))

    @app.get("/admin")
    @admin_required
    def admin_dashboard():
        users = services.list_users()
        pending_reviews = services.list_pending_reviews()
        results = services.list_results({})
        completed = [item for item in results if item["final_score"] is not None]
        average = round(sum(item["final_score"] for item in completed) / len(completed), 1) if completed else None
        return render_template(
            "admin_dashboard.html",
            title="管理看板",
            user_count=len(users),
            pending_user_count=len([u for u in users if u["status"] == "pending"]),
            pending_review_count=len(pending_reviews),
            result_count=len(results),
            average_score=average,
            import_status=app.config.get("IMPORT_STATUS", {}),
        )

    @app.get("/admin/users")
    @admin_required
    def admin_users():
        return render_template(
            "admin_users.html",
            title="人员审核",
            users=services.list_users(
                status=request.args.get("status"),
                region=request.args.get("region"),
                project=request.args.get("project"),
                position=request.args.get("position"),
                keyword=request.args.get("keyword"),
            ),
        )

    @app.post("/admin/users/<int:user_id>/status")
    @admin_required
    @csrf_required
    def admin_set_user_status(user_id):
        services.set_user_status(user_id, request.form["status"])
        return redirect(url_for("admin_users"))

    @app.get("/admin/papers")
    @admin_required
    def admin_papers():
        papers = []
        for paper in services.list_papers():
            paper = dict(paper)
            paper["questions"] = services.get_paper_questions(paper["id"])
            papers.append(paper)
        return render_template(
            "admin_papers.html",
            title="题库管理",
            papers=papers,
            current_exam_paper=services.get_current_exam_paper(),
        )

    @app.post("/admin/papers/current")
    @admin_required
    @csrf_required
    def admin_set_current_paper():
        try:
            services.set_current_exam_paper(int(request.form["paper_id"]))
        except ValueError as exc:
            flash(str(exc))
        else:
            flash("当前考试试卷已更新。")
        return redirect(url_for("admin_papers"))

    @app.route("/admin/review", methods=["GET", "POST"])
    @admin_required
    @csrf_required
    def admin_review():
        if request.method == "POST":
            services.review_answer(
                int(request.form["answer_id"]),
                current_user()["id"],
                float(request.form["final_score"]),
                request.form.get("comment", ""),
            )
            flash("阅卷结果已保存。")
            return redirect(url_for("admin_review"))
        return render_template("admin_review.html", title="阅卷管理", reviews=services.list_pending_reviews())

    @app.post("/admin/review/<int:answer_id>")
    @admin_required
    @csrf_required
    def admin_review_answer(answer_id):
        services.review_answer(
            answer_id,
            current_user()["id"],
            float(request.form["final_score"]),
            request.form.get("comment", ""),
        )
        flash("阅卷结果已保存。")
        return redirect(url_for("admin_review"))

    @app.get("/admin/results")
    @admin_required
    def admin_results():
        filters = dict(request.args)
        return render_template(
            "admin_results.html",
            title="成绩查询",
            results=services.list_results(filters),
            filters=filters,
            papers=services.list_papers(),
        )

    @app.get("/admin/results.csv")
    @admin_required
    def admin_results_csv():
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(["姓名", "手机号", "区域/分公司", "项目部", "岗位", "试卷", "分数", "状态"])
        for row in services.list_results(dict(request.args)):
            writer.writerow(
                [
                    row["user_name"],
                    row["mobile"],
                    row["region"],
                    row["project"],
                    row["position"],
                    row["paper_title"],
                    row["final_score"],
                    row["status"],
                ]
            )
        return Response(output.getvalue(), mimetype="text/csv")

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
