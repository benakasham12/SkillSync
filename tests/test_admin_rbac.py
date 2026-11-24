"""
Comprehensive unit and integration tests for Admin Authorization & RBAC:
1. Admin can edit any project (including projects created by others) without unauthorized error.
2. Admin can delete any project on the platform.
3. Admin can edit any user's profile and account settings.
4. Admin can delete any user account with safe cascading deletion.
5. Admin cannot delete their own account.
6. Normal student user CANNOT edit other users' projects.
7. Normal student user CANNOT delete other users' projects.
8. Normal student user CANNOT access the admin dashboard.
9. Normal student user CANNOT access admin user edit or delete endpoints.
10. Admin dashboard renders all users, all projects, and overview metrics correctly.
"""

import pytest
import tempfile
import os
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import init_db, execute_db, query_db, resolve_db_paths


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    app = create_app(db_path=db_path, test_config={'TESTING': True, 'DATABASE': db_path, 'SECRET_KEY': 'test-secret'})
    yield app

    l_path, u_path = resolve_db_paths(db_path)
    for p in (l_path, u_path, db_path):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


@pytest.fixture
def client(app):
    return app.test_client()


def setup_users_and_projects(app):
    """Seed test admin user, two student users, and a student-owned project."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw = generate_password_hash("password123")

        # Admin user
        admin_id = execute_db(
            "INSERT INTO users (email, password_hash, role, status) VALUES ('admin@bmsit.in', ?, 'admin', 'active')",
            (pw,), db_path=db_path
        )
        execute_db(
            "INSERT INTO student_profiles (user_id, display_name, usn, branch, year, section) VALUES (?, 'Faculty Admin', 'ADM001', 'Faculty', 'N/A', 'ADM')",
            (admin_id,), db_path=db_path
        )

        # Student 1 (creator)
        student1_id = execute_db(
            "INSERT INTO users (email, password_hash, role, status) VALUES ('student1@bmsit.in', ?, 'student', 'active')",
            (pw,), db_path=db_path
        )
        s1_prof = execute_db(
            "INSERT INTO student_profiles (user_id, display_name, usn, branch, year, section) VALUES (?, 'Student One', '1BY23CS001', 'CSE', '1st Year', 'CSE-13')",
            (student1_id,), db_path=db_path
        )

        # Student 2 (other student)
        student2_id = execute_db(
            "INSERT INTO users (email, password_hash, role, status) VALUES ('student2@bmsit.in', ?, 'student', 'active')",
            (pw,), db_path=db_path
        )
        execute_db(
            "INSERT INTO student_profiles (user_id, display_name, usn, branch, year, section) VALUES (?, 'Student Two', '1BY23CS002', 'ISE', '2nd Year', 'ISE-01')",
            (student2_id,), db_path=db_path
        )

        # Project created by student 1
        proj_id = execute_db(
            "INSERT INTO projects (owner_id, title, description, category, status, team_size_min, team_size_max) VALUES (?, 'Student 1 AI Project', 'An innovative AI project', 'Machine Learning', 'published', 2, 4)",
            (student1_id,), db_path=db_path
        )

        # Add team member record for owner
        execute_db(
            "INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'owner')",
            (proj_id, student1_id), db_path=db_path
        )

        return {
            'admin_id': admin_id,
            'student1_id': student1_id,
            'student2_id': student2_id,
            'project_id': proj_id
        }


def test_admin_can_edit_any_project(app, client):
    """Admin can edit projects created by another user without unauthorized error."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']
    proj_id = ids['project_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    # GET edit project
    res_get = client.get(f'/projects/{proj_id}/edit')
    assert res_get.status_code == 200
    assert b"Student 1 AI Project" in res_get.data
    assert b"Unauthorized: You can only edit projects you created" not in res_get.data

    # POST update project
    res_post = client.post(f'/projects/{proj_id}/edit', data={
        'title': 'Updated Title by Administrator',
        'description': 'Updated description',
        'category': 'Web Development',
        'duration': '2\u20133 Months',
        'collaboration_mode': 'Hybrid',
        'availability': 'Flexible',
        'team_size_max': '5'
    }, follow_redirects=True)

    assert res_post.status_code == 200
    assert b"Unauthorized" not in res_post.data

    with app.app_context():
        p = query_db("SELECT title, category FROM projects WHERE id = ?", (proj_id,), one=True, db_path=app.config['DATABASE'])
        assert p['title'] == 'Updated Title by Administrator'
        assert p['category'] == 'Web Development'


def test_admin_can_delete_any_project(app, client):
    """Admin can delete any project on the platform."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']
    proj_id = ids['project_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    res = client.post(f'/admin/projects/{proj_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"deleted successfully" in res.data

    with app.app_context():
        p = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=app.config['DATABASE'])
        assert p is None


def test_admin_can_edit_any_user_profile(app, client):
    """Admin can view and update any student's profile via admin management."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']
    s1_id = ids['student1_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    # GET user edit page
    res_get = client.get(f'/admin/users/{s1_id}/edit')
    assert res_get.status_code == 200
    assert b"Student One" in res_get.data

    # POST updated profile details
    res_post = client.post(f'/admin/users/{s1_id}/edit', data={
        'display_name': 'Student One Modified',
        'usn': '1BY23CS999',
        'branch': 'ISE',
        'year': '2nd Year',
        'section': 'ISE-02',
        'institution': 'BMS Institute of Technology',
        'role': 'student',
        'status': 'active',
        'bio': 'Updated bio by administrator'
    }, follow_redirects=True)

    assert res_post.status_code == 200
    assert b"Profile for Student One Modified updated successfully" in res_post.data

    with app.app_context():
        prof = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (s1_id,), one=True, db_path=app.config['DATABASE'])
        assert prof['display_name'] == 'Student One Modified'
        assert prof['branch'] == 'ISE'
        assert prof['bio'] == 'Updated bio by administrator'


def test_admin_can_delete_user_account(app, client):
    """Admin can delete a user account and cascade deletion cleanly."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']
    s1_id = ids['student1_id']
    proj_id = ids['project_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    res = client.post(f'/admin/users/{s1_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"deleted permanently" in res.data

    with app.app_context():
        db_path = app.config['DATABASE']
        u = query_db("SELECT * FROM users WHERE id = ?", (s1_id,), one=True, db_path=db_path)
        assert u is None
        sp = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (s1_id,), one=True, db_path=db_path)
        assert sp is None
        # Owned project should be removed
        p = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
        assert p is None


def test_admin_cannot_delete_own_account(app, client):
    """Safety guard: Administrator cannot delete their own account."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    res = client.post(f'/admin/users/{admin_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b"Administrators cannot delete their own account" in res.data

    with app.app_context():
        u = query_db("SELECT * FROM users WHERE id = ?", (admin_id,), one=True, db_path=app.config['DATABASE'])
        assert u is not None


def test_normal_user_cannot_edit_other_project(app, client):
    """Normal student cannot edit another student's project."""
    ids = setup_users_and_projects(app)
    s2_id = ids['student2_id']
    proj_id = ids['project_id']

    with client.session_transaction() as sess:
        sess['user_id'] = s2_id
        sess['user_role'] = 'student'
        sess['user_email'] = 'student2@bmsit.in'

    res_get = client.get(f'/projects/{proj_id}/edit', follow_redirects=True)
    assert b"Unauthorized: You can only edit projects you created" in res_get.data

    res_post = client.post(f'/projects/{proj_id}/edit', data={
        'title': 'Hacked Title'
    }, follow_redirects=True)
    assert b"Unauthorized: You can only edit projects you created" in res_post.data

    with app.app_context():
        p = query_db("SELECT title FROM projects WHERE id = ?", (proj_id,), one=True, db_path=app.config['DATABASE'])
        assert p['title'] == 'Student 1 AI Project'


def test_normal_user_cannot_delete_other_project(app, client):
    """Normal student cannot delete another student's project."""
    ids = setup_users_and_projects(app)
    s2_id = ids['student2_id']
    proj_id = ids['project_id']

    with client.session_transaction() as sess:
        sess['user_id'] = s2_id
        sess['user_role'] = 'student'
        sess['user_email'] = 'student2@bmsit.in'

    res = client.post(f'/projects/{proj_id}/delete', follow_redirects=True)
    assert b"Unauthorized" in res.data

    with app.app_context():
        p = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=app.config['DATABASE'])
        assert p is not None


def test_normal_user_cannot_access_admin_dashboard(app, client):
    """Normal student is redirected when trying to access /admin/dashboard."""
    ids = setup_users_and_projects(app)
    s1_id = ids['student1_id']

    with client.session_transaction() as sess:
        sess['user_id'] = s1_id
        sess['user_role'] = 'student'
        sess['user_email'] = 'student1@bmsit.in'

    res = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Administrator privileges required" in res.data


def test_normal_user_cannot_access_admin_management_endpoints(app, client):
    """Normal student cannot call admin user edit or delete endpoints."""
    ids = setup_users_and_projects(app)
    s1_id = ids['student1_id']
    s2_id = ids['student2_id']

    with client.session_transaction() as sess:
        sess['user_id'] = s1_id
        sess['user_role'] = 'student'
        sess['user_email'] = 'student1@bmsit.in'

    res_edit = client.get(f'/admin/users/{s2_id}/edit', follow_redirects=True)
    assert b"Administrator privileges required" in res_edit.data

    res_del = client.post(f'/admin/users/{s2_id}/delete', follow_redirects=True)
    assert b"Administrator privileges required" in res_del.data


def test_admin_dashboard_metrics_and_tables(app, client):
    """Admin dashboard renders user and project management tables and overview metrics."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    res = client.get('/admin/dashboard')
    assert res.status_code == 200
    assert b"User Management" in res.data
    assert b"Project Management" in res.data
    assert b"student1@bmsit.in" in res.data
    assert b"student2@bmsit.in" in res.data
    assert b"Student 1 AI Project" in res.data
    assert b"Total Registered Users" in res.data
    assert b"Total Projects Created" in res.data


def test_cloud_sync_endpoint_requires_admin_authorization(app, client):
    """Verify that /api/cloud/sync requires secure admin authorization and rejects anonymous/normal users."""
    ids = setup_users_and_projects(app)
    admin_id = ids['admin_id']
    student_id = ids['student1_id']

    # 1. Unauthenticated request must return 401
    res_anon = client.post('/api/cloud/sync', json={})
    assert res_anon.status_code == 401
    assert res_anon.get_json().get('error') == 'Authentication required'

    # 2. Normal student request must return 403 Forbidden
    with client.session_transaction() as sess:
        sess['user_id'] = student_id
        sess['user_role'] = 'student'
        sess['user_email'] = 'student1@bmsit.in'

    res_student = client.post('/api/cloud/sync', json={})
    assert res_student.status_code == 403
    assert res_student.get_json().get('error') == 'Administrator privileges required.'

    # 3. Admin request is authorized
    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['user_role'] = 'admin'
        sess['user_email'] = 'admin@bmsit.in'

    # When cloud is not enabled in test environment, sync returns 500 or proper json response, but is NOT rejected with 401/403
    res_admin = client.post('/api/cloud/sync', json={})
    assert res_admin.status_code in (200, 500)
    assert res_admin.status_code not in (401, 403)
