"""
Automated unit tests for PRD FR-09 (Search & Filters), FR-13 (Reporting & Moderation),
and Section 9 (Analytics Summary).
"""

import pytest
import tempfile
import os
from app import create_app
from app.models import init_db, execute_db, query_db
from app.matching import calculate_matches_for_project
from app.analytics import get_analytics_summary
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


def test_candidate_filters_fr_09(app):
    """PRD FR-09: Filter suggestions by skill, section, min_score, fills_gap_only."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw = generate_password_hash("pass123")

        s_python = execute_db("INSERT INTO skills (name, category) VALUES ('Python', 'Backend')", db_path=db_path)
        s_figma = execute_db("INSERT INTO skills (name, category) VALUES ('Figma', 'Design')", db_path=db_path)

        owner_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('owner@bmsit.in', ?)", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, section, is_match_ready) VALUES (?, 'Owner', 'CSE-13', 1)", (owner_id,), db_path=db_path)

        proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'Filter Proj', 'published')", (owner_id,), db_path=db_path)
        execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s_python), db_path=db_path)
        execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s_figma), db_path=db_path)

        # Candidate 1: Section CSE-13, has Python
        c1 = execute_db("INSERT INTO users (email, password_hash) VALUES ('c1@bmsit.in', ?)", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, section, is_match_ready, visibility) VALUES (?, 'Cand 1', 'CSE-13', 1, 'public')", (c1,), db_path=db_path)
        execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (c1, s_python), db_path=db_path)

        # Candidate 2: Section CSE-14, has Figma
        c2 = execute_db("INSERT INTO users (email, password_hash) VALUES ('c2@bmsit.in', ?)", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, section, is_match_ready, visibility) VALUES (?, 'Cand 2', 'CSE-14', 1, 'public')", (c2,), db_path=db_path)
        execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (c2, s_figma), db_path=db_path)

        # Filter by section 'CSE-13'
        res_sec = calculate_matches_for_project(proj_id, filters={'section': 'CSE-13'}, db_path=db_path)
        assert len(res_sec) == 1
        assert res_sec[0]['user_id'] == c1

        # Filter by skill Figma
        res_sk = calculate_matches_for_project(proj_id, filters={'skill_id': str(s_figma)}, db_path=db_path)
        assert len(res_sk) == 1
        assert res_sk[0]['user_id'] == c2


def test_reporting_and_moderation_fr_13(client, app):
    """PRD FR-13: Student submits report, admin resolves and deactivates."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw = generate_password_hash("pass123")

        admin_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('admin@bmsit.in', ?, 'admin')", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Faculty Admin')", (admin_id,), db_path=db_path)

        student_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('student@bmsit.in', ?)", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Student')", (student_id,), db_path=db_path)

        bad_user_id = execute_db("INSERT INTO users (email, password_hash, status) VALUES ('bad@bmsit.in', ?, 'active')", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Spammer')", (bad_user_id,), db_path=db_path)

        # Student submits report
        with client.session_transaction() as sess:
            sess['user_id'] = student_id
            sess['user_role'] = 'student'

        res_rep = client.post('/reports', data={
            'target_type': 'profile',
            'target_id': bad_user_id,
            'reason': 'Spam profile and inappropriate content.'
        }, follow_redirects=True)
        assert res_rep.status_code == 200

        rep = query_db("SELECT * FROM reports WHERE target_id = ?", (bad_user_id,), one=True, db_path=db_path)
        assert rep is not None
        assert rep['status'] == 'pending'

        # Admin resolves report and deactivates user
        with client.session_transaction() as sess:
            sess['user_id'] = admin_id
            sess['user_role'] = 'admin'

        res_resolve = client.post(f'/admin/reports/{rep["id"]}/resolve', data={
            'action': 'resolve',
            'admin_notes': 'Confirmed spam. User deactivated.',
            'take_action': 'deactivate_user'
        }, follow_redirects=True)
        assert res_resolve.status_code == 200

        # Verify report resolved and bad_user deactivated
        rep_after = query_db("SELECT * FROM reports WHERE id = ?", (rep['id'],), one=True, db_path=db_path)
        assert rep_after['status'] == 'resolved'

        bad_user = query_db("SELECT status FROM users WHERE id = ?", (bad_user_id,), one=True, db_path=db_path)
        assert bad_user['status'] == 'deactivated'


def test_analytics_summary_section_9(app):
    """PRD Section 9: Computes North Star & Funnel Metrics."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw = generate_password_hash("pass123")

        u1 = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('u1@bmsit.in', ?, 'student')", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'U1', 1)", (u1,), db_path=db_path)

        u2 = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('u2@bmsit.in', ?, 'student')", (pw,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'U2', 0)", (u2,), db_path=db_path)

        # 1 of 2 match ready -> 50%
        metrics = get_analytics_summary(db_path=db_path)
        assert metrics['total_users'] == 2
        assert metrics['match_ready_profiles'] == 1
        assert metrics['profile_completion_rate'] == 50.0
