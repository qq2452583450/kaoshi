"""Session and role helpers for Flask routes."""

import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for

from .services import get_user


def current_user():
    user_id = session.get("user_id")
    return get_user(user_id) if user_id else None


def generate_csrf_token():
    """Generate and store CSRF token in session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token():
    """Validate CSRF token from form submission."""
    token = request.form.get("csrf_token")
    if not token or token != session.get("csrf_token"):
        abort(403)


def csrf_required(view):
    """Decorator to require CSRF token for POST requests."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        from flask import current_app
        if request.method == "POST" and not current_app.config.get("TESTING"):
            validate_csrf_token()
        return view(*args, **kwargs)
    return wrapped


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
