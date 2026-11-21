"""
Unit and integration tests for SkillSync:
- Project persistence across page refreshes, re-connections, and session reloads.
- Find Teammates authorization: verifies owner access is granted and non-owner access is denied.
- Type-safe comparison: string '123' vs int 123.
- User ID vs Student Profile ID ownership resolution.
- Team members table owner role resolution.
- Visibility of drafts and published projects for creators.
"""

import pytest
import tempfile
import os
from flask import session
from app import create_app
from app.models import init_db, execute_db, query_db
from app.routes.projects import is_project_owner
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    app = create_app(db_path=db_path, test_config={'TESTING': True, 'DATABASE': db_path, 'SECRET_KEY': 'test-secret-key-persistence'})
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def create_student_with_profile(app, email, name, branch='CSE'):
    """Helper to create user and student profile."""
    db_path = app.config['DATABASE']
    pw = generate_password_hash("password123")
    user_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'student')", (email, pw), db_path=db_path)
    prof_id = execute_db("""
        INSERT INTO student_profiles (user_id, display_name, branch, year, section, is_match_ready)
        VALUES (?, ?, ?, '3rd Year', 'CSE-13', 1)
    """, (user_id, name, branch), db_path=db_path)
    return user_id, prof_id


def test_is_project_owner_helper_type_mismatch_and_profile_id(app):
    """Test is_project_owner handles int vs string and user_id vs profile_id."""
    with app.app_context():
        u1, p1 = create_student_with_profile(app, 'owner1@bmsit.in', 'Owner One')
        u2, p2 = create_student_with_profile(app, 'other@bmsit.in', 'Other Student')

        # Project with owner_id = u1 (int)
        db_path = app.config['DATABASE']
        proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'Test Proj', 'published')", (u1,), db_path=db_path)
        proj = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)

        # 1. Direct int match
        assert is_project_owner(proj, u1, db_path=db_path) is True
        # 2. String representation of user_id
        assert is_project_owner(proj, str(u1), db_path=db_path) is True
        # 3. Profile ID of user
        assert is_project_owner(proj, p1, db_path=db_path) is True
        # 4. Another user is NOT owner
        assert is_project_owner(proj, u2, db_path=db_path) is False
        assert is_project_owner(proj, str(u2), db_path=db_path) is False
        assert is_project_owner(proj, None, db_path=db_path) is False

        # 5. Project created with profile_id as owner_id
        proj_p_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'Profile Owner Proj', 'published')", (p1,), db_path=db_path)
        proj_p = query_db("SELECT * FROM projects WHERE id = ?", (proj_p_id,), one=True, db_path=db_path)
        # Should resolve u1 as owner
        assert is_project_owner(proj_p, u1, db_path=db_path) is True
        assert is_project_owner(proj_p, str(u1), db_path=db_path) is True


def test_is_project_owner_team_members_owner_role(app):
    """Test owner authorization through team_members role='owner'."""
    with app.app_context():
        u1, p1 = create_student_with_profile(app, 'owner2@bmsit.in', 'Owner Two')
        db_path = app.config['DATABASE']
        proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (999, 'Delegated Proj', 'published')", db_path=db_path)
        execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'owner')", (proj_id, u1), db_path=db_path)
        proj = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)

        assert is_project_owner(proj, u1, db_path=db_path) is True
        assert is_project_owner(proj, str(u1), db_path=db_path) is True


def test_find_teammates_authorization_owner_allowed_str_and_int(client, app):
    """Owner accessing /projects/<id>/matches is granted access (HTTP 200)."""
    u1, p1 = create_student_with_profile(app, 'founder@bmsit.in', 'Founder User')
    u2, p2 = create_student_with_profile(app, 'stranger@bmsit.in', 'Stranger User')
    db_path = app.config['DATABASE']

    # Project with required skill
    s_id = execute_db("INSERT INTO skills (name, category) VALUES ('React', 'Frontend')", db_path=db_path)
    proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'My Startup', 'published')", (u1,), db_path=db_path)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s_id), db_path=db_path)

    # 1. Logged in as Owner with integer user_id
    with client.session_transaction() as sess:
        sess['user_id'] = u1
        sess['user_email'] = 'founder@bmsit.in'
        sess['user_name'] = 'Founder User'
        sess['user_role'] = 'student'

    res = client.get(f'/projects/{proj_id}/matches')
    assert res.status_code == 200
    assert b"Match Recommendations" in res.data or b"Candidates" in res.data or b"My Startup" in res.data

    # 2. Logged in with string user_id
    with client.session_transaction() as sess:
        sess['user_id'] = str(u1)

    res_str = client.get(f'/projects/{proj_id}/matches')
    assert res_str.status_code == 200
    assert b"Only the project owner can view match recommendations" not in res_str.data

    # 3. API endpoint for owner
    api_res = client.get(f'/api/projects/{proj_id}/matches')
    assert api_res.status_code == 200
    json_data = api_res.get_json()
    assert 'matches' in json_data

    # 4. Stranger is denied access
    with client.session_transaction() as sess:
        sess['user_id'] = u2
        sess['user_email'] = 'stranger@bmsit.in'

    res_denied = client.get(f'/projects/{proj_id}/matches', follow_redirects=True)
    assert b"Only the project owner can view match recommendations for this project" in res_denied.data

    api_denied = client.get(f'/api/projects/{proj_id}/matches')
    assert api_denied.status_code == 403


def test_project_persists_after_creation_and_refresh(client, app):
    """
    BUG 1 Fix Verification:
    Verify that project created via API/form persists to database,
    is fetched on page reloads, and does not disappear after refreshing.
    """
    u1, p1 = create_student_with_profile(app, 'creator@bmsit.in', 'Project Creator')

    with client.session_transaction() as sess:
        sess['user_id'] = u1
        sess['user_email'] = 'creator@bmsit.in'
        sess['user_name'] = 'Project Creator'
        sess['user_role'] = 'student'

    # 1. Create project via POST
    payload = {
        'title': 'AI Traffic Manager',
        'category': 'AI / Machine Learning',
        'duration': '2–3 Months',
        'collaboration_mode': 'Hybrid',
        'availability': 'Flexible',
        'description': 'Smart traffic management system using computer vision',
        'team_size_max': '4',
        'submit_action': 'publish',
        'skills_json': '[{"name": "Python", "priority": "Must Have", "proficiency": "Intermediate"}]'
    }

    res_create = client.post('/projects/create', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_create.status_code in (200, 201)
    create_data = res_create.get_json()
    assert create_data['success'] is True
    proj_id = create_data['project_id']
    assert proj_id > 0

    # 2. Simulate browser reload / GET project detail
    res_detail = client.get(f'/projects/{proj_id}')
    assert res_detail.status_code == 200
    html_detail = res_detail.data.decode('utf-8')
    assert 'AI Traffic Manager' in html_detail
    assert 'Project Creator' in html_detail

    # 3. Simulate refreshing /projects (Find Projects)
    res_list = client.get('/projects')
    assert res_list.status_code == 200
    html_list = res_list.data.decode('utf-8')
    assert 'AI Traffic Manager' in html_list
    assert 'Find Teammates' in html_list

    # 4. Simulate refreshing /my-projects
    res_my = client.get('/my-projects')
    assert res_my.status_code == 200
    html_my = res_my.data.decode('utf-8')
    assert 'AI Traffic Manager' in html_my

    # 5. Simulate browser reload where session is restored via permanent cookie
    # Re-fetch multiple times to simulate multiple page refreshes
    for _ in range(3):
        res_reload = client.get('/projects')
        assert 'AI Traffic Manager' in res_reload.data.decode('utf-8')


def test_draft_project_persists_and_visible_to_owner(client, app):
    """Test that a project saved as Draft persists and remains visible to creator across refreshes."""
    u1, p1 = create_student_with_profile(app, 'draftowner@bmsit.in', 'Draft Owner')

    with client.session_transaction() as sess:
        sess['user_id'] = u1
        sess['user_email'] = 'draftowner@bmsit.in'
        sess['user_name'] = 'Draft Owner'

    payload = {
        'title': 'Secret Robotics Lab Draft',
        'category': 'IoT & Hardware',
        'description': 'Autonomous drone swarm navigation',
        'submit_action': 'draft',
        'skills_json': '[]'
    }

    res = client.post('/projects/create', data=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res.status_code in (200, 201)
    proj_id = res.get_json()['project_id']

    # Refresh /my-projects
    res_my = client.get('/my-projects')
    assert res_my.status_code == 200
    assert 'Secret Robotics Lab Draft' in res_my.data.decode('utf-8')

    # Refresh /projects (all projects tab shows drafts to owner)
    res_all = client.get('/projects')
    assert 'Secret Robotics Lab Draft' in res_all.data.decode('utf-8')
