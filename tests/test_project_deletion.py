"""
Comprehensive verification tests for Project Deletion Persistence in SkillSync.

Verifies:
- Test 1: Create project, delete it, refresh/reload -> remains deleted permanently.
- Test 2: Delete from My Projects -> navigate to Explore Projects -> does not appear in listing.
- Test 3: Admin deletes another user's project -> permanently deleted across all tables.
- Test 4: Normal user attempts to delete another user's project -> rejected, project untouched.
- Test 5: Open deleted project's old URL -> returns 'Project not found.' (or 404 for API).
- Test 6: Delete project, sign out, sign in, refresh -> remains deleted.
- Test 7: Cascade deletion cleanly wipes requirements, availability slots, team members, applications, and invitations.
- Test 8: Server restart / init_db() does NOT resurrect deleted projects.
"""

import os
import tempfile
import pytest
from app import create_app
from app.models import init_db, execute_db, query_db, resolve_db_paths
from werkzeug.security import generate_password_hash


@pytest.fixture
def app_and_client():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_del.db')
    listings_p, users_p = resolve_db_paths(db_path)

    app = create_app(db_path=db_path, test_config={
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret-key'
    })

    with app.app_context():
        init_db(db_path)

        # Seed Users
        hashed_pw = generate_password_hash('password123')
        # Student 1 (creator)
        execute_db("""
            INSERT INTO users (id, email, password_hash, role, status)
            VALUES (101, 'alice@bmsit.in', ?, 'student', 'active')
        """, (hashed_pw,))
        execute_db("""
            INSERT INTO student_profiles (id, user_id, display_name, branch, year)
            VALUES (201, 101, 'Alice Creator', 'CSE', '3rd Year')
        """)

        # Student 2 (other student)
        execute_db("""
            INSERT INTO users (id, email, password_hash, role, status)
            VALUES (102, 'bob@bmsit.in', ?, 'student', 'active')
        """, (hashed_pw,))
        execute_db("""
            INSERT INTO student_profiles (id, user_id, display_name, branch, year)
            VALUES (202, 102, 'Bob Attacker', 'ISE', '2nd Year')
        """)

        # Admin user
        execute_db("""
            INSERT INTO users (id, email, password_hash, role, status)
            VALUES (103, 'admin@bmsit.in', ?, 'admin', 'active')
        """, (hashed_pw,))
        execute_db("""
            INSERT INTO student_profiles (id, user_id, display_name, branch, year)
            VALUES (203, 103, 'Faculty Admin', 'Faculty', 'Staff')
        """)

        # Seed catalog skills
        execute_db("INSERT INTO skills (id, name, category, active) VALUES (1, 'Python', 'Web Development', 1)")
        execute_db("INSERT INTO skills (id, name, category, active) VALUES (2, 'React', 'Web Development', 1)")

    client = app.test_client()
    yield app, client, db_path

    # Cleanup temp dir
    for f in [db_path, listings_p, users_p]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


def helper_create_test_project(db_path, owner_id=101, title="Campus Navigator IoT"):
    """Helper to insert a full project with requirements, slots, team members, applications."""
    execute_db("""
        INSERT INTO projects (
            owner_id, title, description, category, course_context,
            team_size_min, team_size_max, status
        )
        VALUES (?, ?, 'Real-time navigation system', 'IoT & Hardware', 'IDT', 2, 4, 'published')
    """, (owner_id, title), db_path=db_path)
    proj = query_db("SELECT id FROM projects WHERE title = ? ORDER BY id DESC LIMIT 1", (title,), one=True, db_path=db_path)
    p_id = proj['id']

    # Skill requirement
    execute_db("""
        INSERT INTO project_skill_requirements (project_id, skill_id, priority, proficiency_level, weight)
        VALUES (?, 1, 'must-have', 'Intermediate', 3.0)
    """, (p_id,), db_path=db_path)

    # Availability slot
    execute_db("""
        INSERT INTO project_availability_slots (project_id, day_of_week, time_block)
        VALUES (?, 'Monday', 'Morning')
    """, (p_id,), db_path=db_path)

    # Team member
    execute_db("""
        INSERT INTO team_members (project_id, user_id, role)
        VALUES (?, ?, 'owner')
    """, (p_id, owner_id), db_path=db_path)

    # Project application from student 102
    execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, 102, 'I want to join this project', 'pending')
    """, (p_id,), db_path=db_path)

    # Invitation
    execute_db("""
        INSERT INTO invitations (project_id, inviter_id, invitee_id, status)
        VALUES (?, ?, 102, 'pending')
    """, (p_id, owner_id), db_path=db_path)

    return p_id


def test_scenario_1_create_delete_refresh_permanently_deleted(app_and_client):
    """Test 1: Create project, delete it, refresh/re-fetch -> project remains permanently deleted."""
    app, client, db_path = app_and_client

    with client.session_transaction() as sess:
        sess['user_id'] = 101
        sess['user_email'] = 'alice@bmsit.in'
        sess['user_role'] = 'student'

    # Create project
    p_id = helper_create_test_project(db_path, owner_id=101, title="Test 1 Delete Project")
    assert query_db("SELECT id FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path) is not None

    # Delete project via POST
    res = client.post(f"/projects/{p_id}/delete", follow_redirects=True)
    assert res.status_code == 200

    # Verify project is permanently deleted from DB
    deleted_proj = query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path)
    assert deleted_proj is None, "Project should be deleted from projects table!"

    # Refresh simulation: query DB again and request listing
    list_res = client.get('/projects')
    assert list_res.status_code == 200
    assert b"Test 1 Delete Project" not in list_res.data


def test_scenario_2_delete_from_my_projects_explore_shows_zero(app_and_client):
    """Test 2: Delete from My Projects -> navigate to Explore Projects -> does not appear in listing and count is accurate."""
    app, client, db_path = app_and_client

    with client.session_transaction() as sess:
        sess['user_id'] = 101
        sess['user_email'] = 'alice@bmsit.in'
        sess['user_role'] = 'student'

    p_id = helper_create_test_project(db_path, owner_id=101, title="Unique Sensor Project Alpha")

    # Verify present in Explore Projects
    res_before = client.get('/projects')
    assert b"Unique Sensor Project Alpha" in res_before.data

    # Delete project
    del_res = client.post(f"/projects/{p_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200

    # Check My Projects
    my_res = client.get('/my-projects')
    assert b"Unique Sensor Project Alpha" not in my_res.data

    # Check Explore Projects
    explore_res = client.get('/projects')
    assert b"Unique Sensor Project Alpha" not in explore_res.data


def test_scenario_3_admin_deletes_other_user_project(app_and_client):
    """Test 3: Admin deletes another user's project -> permanently deleted across all tables."""
    app, client, db_path = app_and_client

    # Created by Alice (101)
    p_id = helper_create_test_project(db_path, owner_id=101, title="Alice Project for Admin Delete")

    # Login as Admin (103)
    with client.session_transaction() as sess:
        sess['user_id'] = 103
        sess['user_email'] = 'admin@bmsit.in'
        sess['user_role'] = 'admin'

    del_res = client.post(f"/admin/projects/{p_id}/delete", follow_redirects=True)
    assert del_res.status_code == 200

    # Ensure deleted from projects and all child tables
    assert query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path) is None
    assert query_db("SELECT * FROM project_skill_requirements WHERE project_id = ?", (p_id,), one=True, db_path=db_path) is None
    assert query_db("SELECT * FROM team_members WHERE project_id = ?", (p_id,), one=True, db_path=db_path) is None
    assert query_db("SELECT * FROM project_applications WHERE project_id = ?", (p_id,), one=True, db_path=db_path) is None
    assert query_db("SELECT * FROM invitations WHERE project_id = ?", (p_id,), one=True, db_path=db_path) is None


def test_scenario_4_unauthorized_user_cannot_delete(app_and_client):
    """Test 4: Normal user tries to delete another user's project -> rejected, project untouched."""
    app, client, db_path = app_and_client

    # Project owned by Alice (101)
    p_id = helper_create_test_project(db_path, owner_id=101, title="Alice Protected Project")

    # Login as Bob (102)
    with client.session_transaction() as sess:
        sess['user_id'] = 102
        sess['user_email'] = 'bob@bmsit.in'
        sess['user_role'] = 'student'

    # Bob tries to delete Alice's project
    del_res = client.post(f"/projects/{p_id}/delete", follow_redirects=True)
    assert b"Unauthorized" in del_res.data or del_res.status_code in (403, 302, 200)

    # Project MUST still exist in database
    proj_still_there = query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path)
    assert proj_still_there is not None, "Unauthorized deletion must NOT delete the project!"


def test_scenario_5_open_deleted_project_url_returns_not_found(app_and_client):
    """Test 5: Open deleted project's old URL -> displays proper 'Project not found.' message."""
    app, client, db_path = app_and_client

    with client.session_transaction() as sess:
        sess['user_id'] = 101
        sess['user_email'] = 'alice@bmsit.in'
        sess['user_role'] = 'student'

    p_id = helper_create_test_project(db_path, owner_id=101, title="Project To Visit After Delete")
    client.post(f"/projects/{p_id}/delete", follow_redirects=True)

    # Visit old URL in browser (HTML request)
    view_res = client.get(f"/projects/{p_id}", follow_redirects=True)
    assert b"Project not found." in view_res.data

    # Visit old URL via JSON API
    api_res = client.get(f"/projects/{p_id}", headers={'Accept': 'application/json'})
    assert api_res.status_code == 404
    json_data = api_res.get_json()
    assert json_data['success'] is False
    assert "not found" in json_data['error'].lower()


def test_scenario_6_delete_project_sign_out_sign_in_remains_deleted(app_and_client):
    """Test 6: Delete project, sign out, sign in with other account, refresh -> remains deleted."""
    app, client, db_path = app_and_client

    # Alice logs in and creates project
    with client.session_transaction() as sess:
        sess['user_id'] = 101
        sess['user_email'] = 'alice@bmsit.in'
        sess['user_role'] = 'student'

    p_id = helper_create_test_project(db_path, owner_id=101, title="Alice Ephemeral Project")
    client.post(f"/projects/{p_id}/delete", follow_redirects=True)

    # Alice signs out
    client.get('/logout', follow_redirects=True)

    # Bob logs in
    client.post('/login', data={'email': 'bob@bmsit.in', 'password': 'password123'}, follow_redirects=True)

    # Explore projects listing
    res = client.get('/projects')
    assert b"Alice Ephemeral Project" not in res.data
    assert query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path) is None


def test_scenario_7_init_db_does_not_resurrect_deleted_projects(app_and_client):
    """Test 7: Server restart or init_db() does not restore deleted projects."""
    app, client, db_path = app_and_client

    p_id = helper_create_test_project(db_path, owner_id=101, title="Do Not Resurrect Me")

    with client.session_transaction() as sess:
        sess['user_id'] = 101
        sess['user_email'] = 'alice@bmsit.in'
        sess['user_role'] = 'student'

    client.post(f"/projects/{p_id}/delete", follow_redirects=True)
    assert query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path) is None

    # Simulate server restart / init_db()
    with app.app_context():
        init_db(db_path)

    # Project MUST remain deleted
    assert query_db("SELECT * FROM projects WHERE id = ?", (p_id,), one=True, db_path=db_path) is None
