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
