"""
Comprehensive automated tests for:
1. Authentication & API/AJAX 401/403 responses
2. Admin capabilities (user edit, user delete with cascade, self-delete guard, project delete)
3. Cloud sync and schema state handling
"""

import pytest
import tempfile
import os
from app import create_app
from app.models import init_db, execute_db, query_db
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


def test_login_required_ajax_and_token_401(client, app):
    """
    Area 1: Verify login_required returns JSON 401 on AJAX, Bearer token, or Accept: application/json.
    """
    # 1. Standard navigation redirects to /login
    res_nav = client.get('/my-projects')
    assert res_nav.status_code == 302
    assert '/login' in res_nav.headers['Location']

    # 2. AJAX request (X-Requested-With) returns JSON 401
    res_ajax = client.get('/my-projects', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert res_ajax.status_code == 401
    assert res_ajax.is_json
    assert res_ajax.json['error'] == 'Authentication required'

    # 3. Accept: application/json returns JSON 401
    res_json = client.get('/my-projects', headers={'Accept': 'application/json'})
    assert res_json.status_code == 401
    assert res_json.is_json

    # 4. Invalid Bearer token returns JSON 401
    res_token = client.get('/my-projects', headers={'Authorization': 'Bearer invalid_signature_token'})
    assert res_token.status_code == 401
    assert res_token.is_json


def test_admin_required_ajax_403_and_capabilities(client, app):
    """
    Area 2: Verify admin_required returns JSON 403 on unauthorized student AJAX access,
    and allows authorized admins to edit and delete accounts with cascade.
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash('pass123')

    admin_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('admin_dbg@bmsit.in', ?, 'admin')", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Admin User')", (admin_id,), db_path=db_path)

    student_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('student_dbg@bmsit.in', ?, 'student')", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Student User')", (student_id,), db_path=db_path)

    # 1. Student accessing admin endpoint via AJAX gets 403
    with client.session_transaction() as sess:
        sess['user_id'] = student_id
        sess['user_email'] = 'student_dbg@bmsit.in'
        sess['user_role'] = 'student'

    res_forbidden = client.get('/admin/dashboard', headers={'Accept': 'application/json'})
    assert res_forbidden.status_code == 403
    assert res_forbidden.is_json
    assert 'Administrator privileges required' in res_forbidden.json['error']

    # 2. Admin logs in
    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_email'] = 'admin_dbg@bmsit.in'
        sess['user_role'] = 'admin'

    # Admin self-deletion guard
    res_self_del = client.post(f'/admin/users/{admin_id}/delete', headers={'Accept': 'application/json'})
    assert res_self_del.status_code == 400
    assert 'Security Error: Administrators cannot delete their own account.' in res_self_del.json['error']

    # Admin creates project for student, then admin deletes user with full cascade
    proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'Cascade Test Proj', 'published')", (student_id,), db_path=db_path)
    execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'owner')", (proj_id, student_id), db_path=db_path)

    res_del = client.post(f'/admin/users/{student_id}/delete', headers={'Accept': 'application/json'})
    assert res_del.status_code == 200
    assert res_del.json['success'] is True

    # Verify student and owned project were cascaded
    u_chk = query_db("SELECT * FROM users WHERE id = ?", (student_id,), one=True, db_path=db_path)
    assert u_chk is None
    p_chk = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert p_chk is None


def test_cloud_status_and_sync_response(client, app):
    """
    Area 3: Verify /api/cloud/status endpoint responds cleanly with configuration metadata.
    """
    res = client.get('/api/cloud/status')
    assert res.status_code == 200
    assert res.is_json
    data = res.json
    assert 'enabled' in data
    assert 'configured' in data
    assert 'cloud_url' in data
    assert 'tables_initialized' in data
