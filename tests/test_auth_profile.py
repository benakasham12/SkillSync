"""
Automated unit tests for PRD FR-01, FR-02, FR-03, FR-04, FR-12:
Registration, Profile Readiness, Visibility and Privacy guards.
"""

import pytest
import tempfile
import os
from app import create_app
from app.models import init_db, execute_db, query_db
from app.routes.profile import check_and_update_match_readiness
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    app = create_app(db_path=db_path, test_config={'TESTING': True, 'DATABASE': db_path})
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def test_match_readiness_evaluation(app):
    """
    Profile is only match ready if:
    - basic info present (name, branch, year)
    - at least 1 skill declared
    - at least 1 availability block declared
    """
    with app.app_context():
        db_path = app.config['DATABASE']
        pw = generate_password_hash("pass123")

        uid = execute_db("INSERT INTO users (email, password_hash) VALUES ('student@bmsit.in', ?)", (pw,), db_path=db_path)
        execute_db("""
            INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready)
            VALUES (?, 'Student', 'CSE', '1st Year', 0)
        """, (uid,), db_path=db_path)

        # 1. No skills, no slots -> not ready
        assert check_and_update_match_readiness(uid) is False

        # 2. Add skill only -> not ready
        s1 = execute_db("INSERT INTO skills (name, category) VALUES ('React', 'Frontend')", db_path=db_path)
        execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'intermediate')", (uid, s1), db_path=db_path)
        assert check_and_update_match_readiness(uid) is False

        # 3. Add availability slot -> becomes match ready!
        execute_db("INSERT INTO availability_slots (user_id, day_of_week, time_block) VALUES (?, 'Monday', 'Evening (5PM-8PM)')", (uid,), db_path=db_path)
        assert check_and_update_match_readiness(uid) is True

        prof = query_db("SELECT is_match_ready FROM student_profiles WHERE user_id = ?", (uid,), one=True, db_path=db_path)
        assert prof['is_match_ready'] == 1


def test_contact_privacy_guard(client, app):
    """PRD FR-12 & Section 13: Contact info hidden until invitation accepted."""
    db_path = app.config['DATABASE']
    pw = generate_password_hash("pass123")

    # User 1 & User 2
    u1 = execute_db("INSERT INTO users (email, password_hash) VALUES ('u1@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, show_contact_after_accept) VALUES (?, 'User One', 1)", (u1,), db_path=db_path)

    u2 = execute_db("INSERT INTO users (email, password_hash) VALUES ('u2@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, show_contact_after_accept) VALUES (?, 'User Two', 1)", (u2,), db_path=db_path)

    with client.session_transaction() as sess:
        sess['user_id'] = u1
        sess['user_email'] = 'u1@bmsit.in'
        sess['user_name'] = 'User One'
        sess['user_role'] = 'student'

    # User 1 views User 2 profile before any shared team -> email must be protected
    res = client.get(f'/students/{u2}')
    assert b"Direct contact information is protected" in res.data
    assert b"u2@bmsit.in" not in res.data
