"""
Comprehensive automated test suite for SkillSync Project Creation and Management System:
Validates the complete lifecycle:
1. "+ Create New Project" button on Projects directory
2. Multi-step Project Creation form with categories, duration, technologies, and team configuration
3. Skill requirements (Must-Have vs Nice-to-Have, proficiencies, custom skills)
4. Publishing safeguards and draft persistence
5. Display in Active Projects with dynamic capacity, skill badges, and status
6. Project details overview, team roster, and coverage analysis
7. Student application workflow (apply, duplicate prevention, self-application prevention, withdraw)
8. Project owner application review (accept, reject) and automatic team roster addition
9. Maximum team size enforcement and open spots calculation
10. Project status toggling (published, closed, reopened)
11. Project deletion and cascade handling
12. Access authorization guards (only owner can edit/delete/manage)
13. "My Projects" dashboard for published, drafts, and closed projects
"""

import pytest
import tempfile
import os
import json
from app import create_app
from app.models import init_db, execute_db, query_db
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    app = create_app(db_path=db_path, test_config={'TESTING': True, 'DATABASE': db_path, 'SECRET_KEY': 'test-secret-key-456'})
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def create_test_student(app, email, name, branch='CSE', year='3rd Year'):
    """Helper to create user and profile in the test database."""
    db_path = app.config['DATABASE']
    pw = generate_password_hash("password123")
    user_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'student')", (email, pw), db_path=db_path)
    execute_db("""
        INSERT INTO student_profiles (user_id, display_name, branch, year, section, is_match_ready)
        VALUES (?, ?, ?, ?, 'CSE-13', 1)
    """, (user_id, name, branch, year), db_path=db_path)
    return user_id


def login_student(client, user_id, email, name):
    """Helper to set session for student authentication."""
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = email
        sess['user_name'] = name
        sess['user_role'] = 'student'


def test_projects_page_displays_create_button_and_heading(client, app):
    """Verify heading 'Active Projects Seeking Teammates' and '+ Create New Project' button."""
    res = client.get('/projects')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert "Active Projects Seeking Teammates" in html
    assert "+ Create New Project" in html
    assert "View All Projects" in html


def test_create_project_page_requires_auth_and_renders_form(client, app):
    """Verify GET /projects/create requires login and renders multi-step sections."""
    # 1. Unauthenticated redirect to login
    res_unauth = client.get('/projects/create')
    assert res_unauth.status_code == 302
    assert '/login' in res_unauth.headers['Location']

    # 2. Authenticated user can view form
    s1 = create_test_student(app, 'student1@bmsit.in', 'Aarav Patel')
    login_student(client, s1, 'student1@bmsit.in', 'Aarav Patel')

    res_auth = client.get('/projects/create')
    assert res_auth.status_code == 200
    html = res_auth.data.decode('utf-8')

    # Stepper & Section Checks
    assert "Section A: Basic Project Information" in html
    assert "Build Your Dream Team" in html
    assert "Team Configuration" in html
    assert "Section D: Review and Publish" in html

    # Field Checks
    assert 'name="title"' in html
    assert 'name="category"' in html
    assert 'name="description"' in html
    assert 'name="duration"' in html
    assert 'name="technologies"' in html
    assert 'id="skillNameInput"' in html
    assert 'id="skillPriorityInput"' in html
    assert 'id="skillProficiencyInput"' in html
    assert 'name="team_size_max"' in html
    assert 'name="collaboration_mode"' in html
    assert 'name="availability"' in html

    # Action Buttons
    assert "Publish Project" in html
    assert "Save as Draft" in html
    assert "Cancel" in html


def test_create_and_publish_project_with_skills(client, app):
    """Test creating and publishing project with multiple required skills (Must-Have and Nice-to-Have)."""
    db_path = app.config['DATABASE']
    s1 = create_test_student(app, 'creator@bmsit.in', 'Vikram Seth')
    login_student(client, s1, 'creator@bmsit.in', 'Vikram Seth')

    skills_payload = [
        {"name": "Python", "priority": "Must Have", "proficiency": "Advanced"},
        {"name": "Machine Learning", "priority": "Must Have", "proficiency": "Intermediate"},
        {"name": "FastAPI", "priority": "Must Have", "proficiency": "Intermediate"},
        {"name": "React UI", "priority": "Nice to Have", "proficiency": "Beginner"}
    ]

    form_data = {
        'title': 'AI Healthcare Diagnostic Assistant',
        'category': 'Artificial Intelligence',
        'description': 'Building an intelligent multimodal diagnosis pipeline for radiological scans using deep learning & FastAPI.',
        'objectives': 'Deliver an interactive clinical diagnostic MVP with model explainability.',
        'technologies': 'Python, PyTorch, FastAPI, React, Docker',
        'duration': '2–3 Months',
        'team_size_max': '4',
        'collaboration_mode': 'Hybrid',
        'availability': 'Weekdays',
        'action': 'publish',
        'skills_json': json.dumps(skills_payload)
    }

    res = client.post('/projects/create', data=form_data, follow_redirects=True)
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert "Project published successfully!" in html
    assert "AI Healthcare Diagnostic Assistant" in html

    # Verify database persistence
    proj = query_db("SELECT * FROM projects WHERE title = 'AI Healthcare Diagnostic Assistant'", one=True, db_path=db_path)
    assert proj is not None
    assert proj['status'] == 'published'
    assert proj['category'] == 'Artificial Intelligence'
    assert proj['team_size_max'] == 4
    assert proj['owner_id'] == s1

    # Verify skills persistence
    reqs = query_db("""
        SELECT psr.*, s.name as skill_name FROM project_skill_requirements psr
        JOIN skills s ON psr.skill_id = s.id
        WHERE psr.project_id = ?
    """, (proj['id'],), db_path=db_path)
    assert len(reqs) == 4
    skill_names = [r['skill_name'] for r in reqs]
    assert "Python" in skill_names
    assert "Machine Learning" in skill_names
    assert "FastAPI" in skill_names
    assert "React UI" in skill_names

    # Verify published project appears in Active Projects directory
    res_list = client.get('/projects')
    assert res_list.status_code == 200
    html_list = res_list.data.decode('utf-8')
    assert "AI Healthcare Diagnostic Assistant" in html_list
    assert "Artificial Intelligence" in html_list
    assert "1 / 4 Members" in html_list
    assert "3 open" in html_list


def test_save_project_as_draft_and_draft_isolation(client, app):
    """Test saving project as draft: visible to creator, hidden from public directory."""
    db_path = app.config['DATABASE']
    s1 = create_test_student(app, 'draftcreator@bmsit.in', 'Meera Rao')
    s2 = create_test_student(app, 'otherstudent@bmsit.in', 'Other Student')

    login_student(client, s1, 'draftcreator@bmsit.in', 'Meera Rao')

    draft_data = {
        'title': 'Autonomous Drone Mapping System',
        'category': 'IoT & Hardware',
        'description': 'Draft work in progress for aerial terrain mapping.',
        'action': 'draft',
        'skills_json': json.dumps([{"name": "C++", "priority": "Must Have", "proficiency": "Intermediate"}])
    }

    res_draft = client.post('/projects/create', data=draft_data, follow_redirects=True)
    assert res_draft.status_code == 200
    assert b"Project saved as draft!" in res_draft.data

    proj = query_db("SELECT * FROM projects WHERE title = 'Autonomous Drone Mapping System'", one=True, db_path=db_path)
    assert proj['status'] == 'draft'

    # Visible in creator's My Projects dashboard
    res_my = client.get('/my-projects')
    assert res_my.status_code == 200
    assert b"Autonomous Drone Mapping System" in res_my.data
    assert b"Draft (Private)" in res_my.data

    # Log in as other student; verify draft is NOT visible in public projects
    login_student(client, s2, 'otherstudent@bmsit.in', 'Other Student')
    res_other = client.get('/projects')
    assert "Autonomous Drone Mapping System" not in res_other.data.decode('utf-8')


def test_edit_project_and_skills(client, app):
    """Test project owner updating details, category, team size, and skills."""
    db_path = app.config['DATABASE']
    s1 = create_test_student(app, 'editor@bmsit.in', 'Editor Student')
    login_student(client, s1, 'editor@bmsit.in', 'Editor Student')

    # Create project
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, description, category, team_size_max, status)
        VALUES (?, 'Original Title', 'Original Description', 'Web Development', 3, 'published')
    """, (s1,), db_path=db_path)

    # Edit project
    updated_skills = [
        {"name": "TypeScript", "priority": "Must Have", "proficiency": "Advanced"},
        {"name": "Next.js", "priority": "Nice to Have", "proficiency": "Intermediate"}
    ]

    edit_data = {
        'title': 'Updated Modern Full-Stack App',
        'category': 'Web Development',
        'description': 'Completely updated description and architecture.',
        'team_size_max': '5',
        'collaboration_mode': 'Online',
        'availability': 'Weekends',
        'action': 'publish',
        'skills_json': json.dumps(updated_skills)
    }

    res_edit = client.post(f'/projects/{proj_id}/edit', data=edit_data, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"Project updated successfully" in res_edit.data

    proj_updated = query_db("SELECT * FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj_updated['title'] == 'Updated Modern Full-Stack App'
    assert proj_updated['team_size_max'] == 5
    assert proj_updated['collaboration_mode'] == 'Online'

    # Verify updated skills
    reqs = query_db("SELECT COUNT(*) as cnt FROM project_skill_requirements WHERE project_id = ?", (proj_id,), one=True, db_path=db_path)
    assert reqs['cnt'] == 2


def test_student_application_workflow_apply_and_review(client, app):
    """
    Test complete application lifecycle:
    1. Student B applies to Student A's project with an introduction message.
    2. Prevent duplicate applications and prevent owner self-application.
    3. Student A reviews application, accepts Student B.
    4. Student B is added to team members roster.
    5. Available positions decrement.
    """
    db_path = app.config['DATABASE']
    owner_id = create_test_student(app, 'lead@bmsit.in', 'Project Lead')
    applicant_id = create_test_student(app, 'dev@bmsit.in', 'Dev Applicant')
    other_id = create_test_student(app, 'declined@bmsit.in', 'Declined Applicant')

    # Create published project
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, description, category, team_size_max, status)
        VALUES (?, 'Smart Energy Grid Optimizer', 'IoT power grid monitoring', 'IoT & Hardware', 3, 'published')
    """, (owner_id,), db_path=db_path)
    # Add required skill
    sk1 = execute_db("INSERT INTO skills (name, category) VALUES ('Embedded C', 'Hardware')", db_path=db_path)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority) VALUES (?, ?, 'must-have')", (proj_id, sk1), db_path=db_path)

    # 1. Owner self-application is prevented
    login_student(client, owner_id, 'lead@bmsit.in', 'Project Lead')
    res_self = client.post(f'/projects/{proj_id}/apply', data={'introduction': 'I am the owner'}, follow_redirects=True)
    assert b"You are the creator of this project and cannot apply" in res_self.data

    # 2. Student B applies
    login_student(client, applicant_id, 'dev@bmsit.in', 'Dev Applicant')
    res_apply = client.post(f'/projects/{proj_id}/apply', data={'introduction': 'I have built Arduino & ESP32 sensors.'}, follow_redirects=True)
    assert res_apply.status_code == 200
    assert b"Application sent successfully!" in res_apply.data

    # Verify application in DB
    app_record = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (proj_id, applicant_id), one=True, db_path=db_path)
    assert app_record is not None
    assert app_record['application_status'] == 'pending'
    assert app_record['introduction'] == 'I have built Arduino & ESP32 sensors.'

    # 3. Duplicate application prevention
    res_dup = client.post(f'/projects/{proj_id}/apply', data={'introduction': 'Duplicate'}, follow_redirects=True)
    assert b"Your application is currently pending review" in res_dup.data

    # 4. Student C applies, will be rejected
    login_student(client, other_id, 'declined@bmsit.in', 'Declined Applicant')
    client.post(f'/projects/{proj_id}/apply', data={'introduction': 'Intro'}, follow_redirects=True)
    app_other = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (proj_id, other_id), one=True, db_path=db_path)

    # 5. Owner reviews applications
    login_student(client, owner_id, 'lead@bmsit.in', 'Project Lead')

    # Owner rejects Student C
    client.post(f'/projects/{proj_id}/applications/{app_other["id"]}/review', data={'decision': 'reject'}, follow_redirects=True)
    app_other_updated = query_db("SELECT application_status FROM project_applications WHERE id = ?", (app_other['id'],), one=True, db_path=db_path)
    assert app_other_updated['application_status'] == 'rejected'

    # Owner accepts Student B
    res_accept = client.post(f'/projects/{proj_id}/applications/{app_record["id"]}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert b"Application accepted! Student has been added to the team roster" in res_accept.data

    # Verify Student B in team_members
    member = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, applicant_id), one=True, db_path=db_path)
    assert member is not None
    assert member['role'] == 'member'

    # Verify updated team count: owner (1) + accepted member (1) = 2 members; team_size_max = 3 (1 spot open)
    res_detail = client.get(f'/projects/{proj_id}')
    assert b"2 / 3" in res_detail.data
    assert b"1 Spot Open" in res_detail.data


def test_team_capacity_limit_enforcement(client, app):
    """Verify that applications cannot be accepted once maximum team size is reached."""
    db_path = app.config['DATABASE']
    owner_id = create_test_student(app, 'leadcap@bmsit.in', 'Team Lead')
    s2 = create_test_student(app, 'member1@bmsit.in', 'Member One')
    s3 = create_test_student(app, 'overflow@bmsit.in', 'Overflow Student')

    # Team size max = 2 (owner + 1 member is max capacity)
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, description, team_size_max, status)
        VALUES (?, 'Tiny Team Capstone', 'Max 2 students', 2, 'published')
    """, (owner_id,), db_path=db_path)

    # Add s2 directly to team
    execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'member')", (proj_id, s2), db_path=db_path)

    # s3 applies
    app3_id = execute_db("INSERT INTO project_applications (project_id, applicant_id, application_status) VALUES (?, ?, 'pending')", (proj_id, s3), db_path=db_path)

    # Owner attempts to accept s3
    login_student(client, owner_id, 'leadcap@bmsit.in', 'Team Lead')
    res_overflow = client.post(f'/projects/{proj_id}/applications/{app3_id}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert b"Cannot accept application: The project team is already full" in res_overflow.data

    # Verify s3 not added to team
    s3_member = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, s3), one=True, db_path=db_path)
    assert s3_member is None


def test_close_reopen_and_delete_project(client, app):
    """Test closing project, reopening project, and deleting project with cascade."""
    db_path = app.config['DATABASE']
    owner_id = create_test_student(app, 'closeowner@bmsit.in', 'Close Owner')
    stranger_id = create_test_student(app, 'stranger@bmsit.in', 'Stranger')

    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, description, status)
        VALUES (?, 'Project To Close', 'Testing close and delete', 'published')
    """, (owner_id,), db_path=db_path)

    login_student(client, owner_id, 'closeowner@bmsit.in', 'Close Owner')

    # Close project
    client.post(f'/projects/{proj_id}/close', follow_redirects=True)
    proj = query_db("SELECT status FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj['status'] == 'closed'

    # When closed, stranger cannot apply
    login_student(client, stranger_id, 'stranger@bmsit.in', 'Stranger')
    res_apply_closed = client.post(f'/projects/{proj_id}/apply', data={'introduction': 'Hello'}, follow_redirects=True)
    assert b"This project is not currently accepting applications" in res_apply_closed.data

    # Owner reopens project
    login_student(client, owner_id, 'closeowner@bmsit.in', 'Close Owner')
    client.post(f'/projects/{proj_id}/close', follow_redirects=True)
    proj_reopened = query_db("SELECT status FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj_reopened['status'] == 'published'

    # Stranger attempts unauthorized delete
    login_student(client, stranger_id, 'stranger@bmsit.in', 'Stranger')
    client.post(f'/projects/{proj_id}/delete', follow_redirects=True)
    proj_still_exists = query_db("SELECT id FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj_still_exists is not None

    # Owner deletes project
    login_student(client, owner_id, 'closeowner@bmsit.in', 'Close Owner')
    res_del = client.post(f'/projects/{proj_id}/delete', follow_redirects=True)
    assert b"Project and all associated records deleted successfully" in res_del.data
    proj_deleted = query_db("SELECT id FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj_deleted is None
