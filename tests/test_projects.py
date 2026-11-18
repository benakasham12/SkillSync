"""
Automated unit tests for PRD FR-05, FR-06: Project creation, skill requirements, and publishing safeguards.
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


def test_empty_requirements_cannot_be_published(client, app):
    """PRD FR-06: Empty requirements cannot be published."""
    db_path = app.config['DATABASE']
    pw = generate_password_hash("pass123")

    owner_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('owner@bmsit.in', ?)", (pw,), db_path=db_path)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Owner')", (owner_id,), db_path=db_path)

    # Create project in draft with no skill requirements
    proj_id = execute_db("INSERT INTO projects (owner_id, title, status) VALUES (?, 'Draft Project', 'draft')", (owner_id,), db_path=db_path)

    with client.session_transaction() as sess:
        sess['user_id'] = owner_id
        sess['user_email'] = 'owner@bmsit.in'
        sess['user_name'] = 'Owner'
        sess['user_role'] = 'student'

    # Attempt to publish empty project
    res = client.post(f'/projects/{proj_id}/publish', follow_redirects=True)
    assert b"Cannot publish project: You must declare at least one required skill first" in res.data
    proj = query_db("SELECT status FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj['status'] == 'draft'

    # Add required skill
    s1 = execute_db("INSERT INTO skills (name, category) VALUES ('Python', 'Backend')", db_path=db_path)
    client.post(f'/projects/{proj_id}/requirements', data={'action': 'add', 'skill_id': s1, 'priority': 'must-have'}, follow_redirects=True)

    # Now publish should succeed
    res_pub = client.post(f'/projects/{proj_id}/publish', follow_redirects=True)
    assert b"Project published" in res_pub.data
    proj_pub = query_db("SELECT status FROM projects WHERE id = ?", (proj_id,), one=True, db_path=db_path)
    assert proj_pub['status'] == 'published'
