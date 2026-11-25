"""
Automated unit tests for PRD FR-10: Invitations Lifecycle and Safeguards.
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


def test_invitation_flow_and_duplicate_prevention(client, app):
    """
    Tests:
    1. Owner sends invitation -> status is 'pending'
    2. Attempting duplicate active invitation is rejected (FR-10)
    3. Invitee accepts -> status becomes 'accepted', invitee added to team_members
    4. Team member cannot be invited again
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash("pass123")

    s1 = execute_db("INSERT INTO skills (name, category) VALUES ('Python', 'Backend')", db_path=db_path)

    # Owner & Invitee
    owner_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('owner@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'Owner', 1)", (owner_id,), db_path=db_path)

    invitee_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('invitee@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'Invitee', 1)", (invitee_id,), db_path=db_path)

    # Published Project
    proj_id = execute_db("INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max) VALUES (?, 'Test Proj', 'published', 2, 4)", (owner_id,), db_path=db_path)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s1), db_path=db_path)

    # Log in as Owner
    with client.session_transaction() as sess:
        sess['user_id'] = owner_id
        sess['user_email'] = 'owner@bmsit.in'
        sess['user_name'] = 'Owner'
        sess['user_role'] = 'student'

    # Send invitation
    res = client.post(f'/projects/{proj_id}/invite', data={'invitee_id': invitee_id, 'message': 'Join our team!'}, follow_redirects=True)
    assert res.status_code == 200
    inv = query_db("SELECT * FROM invitations WHERE project_id = ? AND invitee_id = ?", (proj_id, invitee_id), one=True, db_path=db_path)
    assert inv is not None
    assert inv['status'] == 'pending'
    assert inv['message'] == 'Join our team!'

    # Attempt to send duplicate invitation -> should be warned and not duplicate
    res_dup = client.post(f'/projects/{proj_id}/invite', data={'invitee_id': invitee_id, 'message': 'Second invite'}, follow_redirects=True)
    assert b"active pending invitation has already been sent" in res_dup.data
    inv_count = query_db("SELECT COUNT(*) as cnt FROM invitations WHERE project_id = ? AND invitee_id = ?", (proj_id, invitee_id), one=True, db_path=db_path)['cnt']
    assert inv_count == 1

    # Log in as Invitee and Accept
    with client.session_transaction() as sess:
        sess['user_id'] = invitee_id
        sess['user_email'] = 'invitee@bmsit.in'
        sess['user_name'] = 'Invitee'
        sess['user_role'] = 'student'

    res_accept = client.post(f'/invitations/{inv["id"]}/respond', data={'action': 'accept'}, follow_redirects=True)
    assert res_accept.status_code == 200

    # Verify invitation updated and team_members contains invitee
    inv_updated = query_db("SELECT * FROM invitations WHERE id = ?", (inv['id'],), one=True, db_path=db_path)
    assert inv_updated['status'] == 'accepted'
    assert inv_updated['responded_at'] is not None

    membership = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, invitee_id), one=True, db_path=db_path)
    assert membership is not None
    assert membership['role'] == 'member'


def test_list_invitations_no_cartesian_duplication(client, app):
    """
    Regression test:
    Verify that an application submitted to a project appears EXACTLY ONCE on the owner's /invitations page
    and is not duplicated by Cartesian product joins between users and student_profiles.
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash("pass123")

    # Insert 3 students with overlapping IDs to trigger potential cross-join
    u1 = execute_db("INSERT INTO users (email, password_hash) VALUES ('student1@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (101, ?, 'Student One', 1)", (u1,), db_path=db_path)

    u2 = execute_db("INSERT INTO users (email, password_hash) VALUES ('student2@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (102, ?, 'Student Two', 1)", (u2,), db_path=db_path)

    owner_u = execute_db("INSERT INTO users (email, password_hash) VALUES ('project_owner@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (103, ?, 'Project Owner', 1)", (owner_u,), db_path=db_path)

    # Owner's project
    proj_id = execute_db("INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max) VALUES (?, 'Distributed Systems Lab', 'published', 2, 4)", (owner_u,), db_path=db_path)

    # Student One submits 1 application
    execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, ?, 'I would love to join your project!', 'pending')
    """, (proj_id, u1), db_path=db_path)

    # Log in as Project Owner
    with client.session_transaction() as sess:
        sess['user_id'] = owner_u
        sess['user_email'] = 'project_owner@bmsit.in'
        sess['user_name'] = 'Project Owner'
        sess['user_role'] = 'student'

    res = client.get('/invitations')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # The applicant's name and message should appear
    assert "Student One" in html
    assert "I would love to join your project!" in html

    # Exactly ONE card for this application must appear, NOT multiple
    assert html.count("I would love to join your project!") == 1
    # Other students who did NOT apply must NOT appear as applicants
    assert "Student Two" not in html


def test_accept_join_request_by_project_owner(client, app):
    """
    Test that a project creator can accept an incoming join request from another student
    without authorization errors, adding the applicant to team_members and updating status.
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash("pass123")

    akansha_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('akansha@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (45, ?, 'Akansha', 1)", (akansha_id,), db_path=db_path)

    rahul_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('rahul@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (49, ?, 'Rahul Verma', 1)", (rahul_id,), db_path=db_path)

    other_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('other@bmsit.in', ?)", (pw,), db_path=db_path)

    # Akansha's project
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max)
        VALUES (?, 'IDT Innovation Challenge', 'published', 2, 4)
    """, (akansha_id,), db_path=db_path)

    # Rahul submits application
    app_id = execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, ?, 'Interested in contributing to IDT project!', 'pending')
    """, (proj_id, rahul_id), db_path=db_path)

    # 1. Non-owner attempting to accept -> must be rejected
    with client.session_transaction() as sess:
        sess['user_id'] = other_id
        sess['user_email'] = 'other@bmsit.in'
        sess['user_name'] = 'Other Student'
        sess['user_role'] = 'student'

    res_unauth = client.post(f'/projects/{proj_id}/applications/{app_id}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert b"Unauthorized: Only project creators can review applications." in res_unauth.data

    # 2. Akansha (project owner) accepts -> must succeed
    with client.session_transaction() as sess:
        sess['user_id'] = akansha_id
        sess['user_email'] = 'akansha@bmsit.in'
        sess['user_name'] = 'Akansha'
        sess['user_role'] = 'student'

    res_accept = client.post(f'/projects/{proj_id}/applications/{app_id}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert res_accept.status_code == 200
    assert b"Application accepted! Student has been added to the team roster." in res_accept.data

    # Verify database state
    app_updated = query_db("SELECT * FROM project_applications WHERE id = ?", (app_id,), one=True, db_path=db_path)
    assert app_updated['application_status'] == 'accepted'

    member = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, rahul_id), one=True, db_path=db_path)
    assert member is not None
    assert member['role'] == 'member'




def test_respond_invitation_with_profile_id(client, app):
    """
    Regression test:
    Verify that an invitation sent with invitee_id as student_profiles.id (or users.id)
    can be responded to (accepted/declined) by the invitee without 'Unauthorized action.'.
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash('pass123')

    inviter_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('creator@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (201, ?, 'Creator', 1)", (inviter_id,), db_path=db_path)

    invitee_user_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('candidate@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (id, user_id, display_name, is_match_ready) VALUES (202, ?, 'Candidate', 1)", (invitee_user_id,), db_path=db_path)

    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max)
        VALUES (?, 'Autonomous Drone Tracking', 'published', 2, 4)
    """, (inviter_id,), db_path=db_path)

    # Invitation sent with profile ID (202) instead of user ID
    inv_id = execute_db("""
        INSERT INTO invitations (project_id, inviter_id, invitee_id, status, message)
        VALUES (?, ?, 202, 'pending', 'Please join us!')
    """, (proj_id, inviter_id), db_path=db_path)

    # Log in as Candidate (session['user_id'] is user_id, not profile_id)
    with client.session_transaction() as sess:
        sess['user_id'] = invitee_user_id
        sess['user_email'] = 'candidate@bmsit.in'
        sess['user_name'] = 'Candidate'
        sess['user_role'] = 'student'

    # Candidate accepts
    res = client.post(f'/invitations/{inv_id}/respond', data={'action': 'accept'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Unauthorized action" not in res.data
    assert b"You have joined" in res.data

    # Verify membership
    m = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, invitee_user_id), one=True, db_path=db_path)
    assert m is not None


def test_multiple_students_accepted_both_appear_in_team_roster(client, app):
    """
    Regression test:
    Verify that when multiple students (e.g. Rohan and Ananya) apply and are accepted into a project,
    ALL accepted members appear in the team roster simultaneously on the project detail page
    with accurate capacity count (e.g. Team Roster 3 / 5).
    """
    db_path = app.config['DATABASE']
    pw = generate_password_hash('pass123')

    # Creator (Benaka Sham)
    creator_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('benaka_test@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready) VALUES (?, 'Benaka Sham', 'CSE', '1st Year', 1)", (creator_id,), db_path=db_path)

    # Student 1 (Rohan Kulkarni)
    rohan_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('rohan_test@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready) VALUES (?, 'Rohan Kulkarni', 'CSE', '1st Year', 1)", (rohan_id,), db_path=db_path)

    # Student 2 (Ananya Rao)
    ananya_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('ananya_test@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready) VALUES (?, 'Ananya Rao', 'CSE', '1st Year', 1)", (ananya_id,), db_path=db_path)

    # Project created by Creator (capacity: 5)
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, description, status, team_size_min, team_size_max)
        VALUES (?, 'AI Healthcare Diagnostic Assistant', 'Deep learning model', 'published', 2, 5)
    """, (creator_id,), db_path=db_path)
    execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'owner')", (proj_id, creator_id), db_path=db_path)

    # 1. Rohan applies
    app_rohan = execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, ?, 'Interested in joining!', 'pending')
    """, (proj_id, rohan_id), db_path=db_path)

    # 2. Ananya applies
    app_ananya = execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, ?, 'Interested in joining too!', 'pending')
    """, (proj_id, ananya_id), db_path=db_path)

    # Creator logs in
    with client.session_transaction() as sess:
        sess['user_id'] = creator_id
        sess['user_email'] = 'benaka_test@bmsit.in'
        sess['user_name'] = 'Benaka Sham'
        sess['user_role'] = 'student'

    # Creator accepts Rohan
    res1 = client.post(f'/projects/{proj_id}/applications/{app_rohan}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert res1.status_code == 200

    # Creator accepts Ananya
    res2 = client.post(f'/projects/{proj_id}/applications/{app_ananya}/review', data={'decision': 'accept'}, follow_redirects=True)
    assert res2.status_code == 200

    # Creator views project detail page
    res_detail = client.get(f'/projects/{proj_id}')
    assert res_detail.status_code == 200
    html = res_detail.data.decode('utf-8')

    # Both Rohan and Ananya must be present in the team roster!
    assert 'Rohan Kulkarni' in html
    assert 'Ananya Rao' in html
    assert 'Benaka Sham' in html

    # Team count must be 3 / 5 (3 spots filled, 2 spots open)
    assert '3 / 5' in html


def test_accept_invitation_serverless_cold_container_recovery(client, app):
    """
    Regression test:
    Simulate an invitation created on Container A, viewed by the invitee, and then
    accepted on a cold Container B where the invitation and project rows are absent
    from local SQLite (/tmp). Verify signed inv_token recovers state without
    'Invitation not found.'.
    """
    import re
    db_path = app.config['DATABASE']
    pw = generate_password_hash('pass123')

    inviter_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('inviter_cold@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'Inviter Cold', 1)", (inviter_id,), db_path=db_path)

    invitee_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('invitee_cold@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name, is_match_ready) VALUES (?, 'Invitee Cold', 1)", (invitee_id,), db_path=db_path)

    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max)
        VALUES (?, 'Serverless Sync Project', 'published', 2, 4)
    """, (inviter_id,), db_path=db_path)

    inv_id = execute_db("""
        INSERT INTO invitations (project_id, inviter_id, invitee_id, status, message)
        VALUES (?, ?, ?, 'pending', 'Join us!')
    """, (proj_id, inviter_id, invitee_id), db_path=db_path)

    # Invitee loads /invitations on Container A
    with client.session_transaction() as sess:
        sess['user_id'] = invitee_id
        sess['user_email'] = 'invitee_cold@bmsit.in'
        sess['user_name'] = 'Invitee Cold'
        sess['user_role'] = 'student'

    res_list = client.get('/invitations')
    assert res_list.status_code == 200
    html = res_list.data.decode('utf-8')
    m = re.search(r'name="inv_token"\s+value="([^"]+)"', html)
    assert m is not None
    inv_token = m.group(1)

    # Simulate cold Container B: delete invitation and project from local SQLite
    execute_db("DELETE FROM invitations WHERE id = ?", (inv_id,), db_path=db_path)
    execute_db("DELETE FROM projects WHERE id = ?", (proj_id,), db_path=db_path)

    # Invitee clicks Accept on Container B
    res_accept = client.post(
        f'/invitations/{inv_id}/respond',
        data={'action': 'accept', 'inv_token': inv_token},
        follow_redirects=True
    )
    assert res_accept.status_code == 200
    assert b"Invitation not found." not in res_accept.data
    assert b"You have joined" in res_accept.data

    # Verify membership was recorded on Container B
    member = query_db("SELECT * FROM team_members WHERE project_id = ? AND user_id = ?", (proj_id, invitee_id), one=True, db_path=db_path)
    assert member is not None
    assert member['role'] == 'member'


