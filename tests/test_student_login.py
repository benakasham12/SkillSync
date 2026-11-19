"""
Automated unit and integration test suite for the SkillSync Student Login System:
Validates design elements, required fields, validation rules, authentication,
session persistence, protected routes, logout, and forgot/reset password flows.
"""

import pytest
import tempfile
import os
from app import create_app
from app.models import init_db, execute_db, query_db
from werkzeug.security import generate_password_hash, check_password_hash


@pytest.fixture
def app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(db_path)

    app = create_app(db_path=db_path, test_config={'TESTING': True, 'DATABASE': db_path, 'SECRET_KEY': 'test-secret-key-123'})
    yield app

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


def test_student_login_page_renders_design_and_fields(client):
    """Verify GET /login returns 200 and renders all required SaaS design and form elements."""
    response = client.get('/login')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Left Section Brand & Hero elements
    assert "Welcome Back to SkillSync!" in html
    assert "Your team, your skills, your next big idea" in html
    assert "collab-illustration-svg" in html or "svg" in html

    # Right Section Form elements
    assert "Student Login" in html
    assert "Sign in to your SkillSync account." in html
    assert 'name="email"' in html
    assert "Student Email" in html
    assert "Enter your college or registered email" in html
    assert 'name="password"' in html
    assert "Password" in html
    assert "Enter your password" in html
    assert 'id="togglePasswordBtn"' in html or "btn-toggle-password" in html
    assert "Remember Me" in html
    assert 'name="remember"' in html
    assert "Forgot Password?" in html
    assert "/forgot-password" in html
    assert "Sign In" in html

    # Footer navigation
    assert "Don't have an account?" in html
    assert "Create Student Account" in html
    assert "/register" in html


def test_login_field_validation_and_invalid_credentials(client, app):
    """Verify validation for empty inputs, malformed emails, and invalid credentials."""
    # 1. Empty submission
    res_empty = client.post('/login', data={'email': '', 'password': ''}, follow_redirects=True)
    assert res_empty.status_code == 200
    assert b"Please enter both your student email and password." in res_empty.data

    # 2. Malformed email format
    res_bad_email = client.post('/login', data={'email': 'notanemail', 'password': 'pass'}, follow_redirects=True)
    assert res_bad_email.status_code == 200
    assert b"Please enter a valid student email address format." in res_bad_email.data

    # 3. Non-existent account
    res_not_found = client.post('/login', data={'email': 'nonexistent@bmsit.in', 'password': 'password123'}, follow_redirects=True)
    assert res_not_found.status_code == 200
    assert b"Invalid email or password" in res_not_found.data

    # 4. Wrong password
    with app.app_context():
        db_path = app.config['DATABASE']
        pw_hash = generate_password_hash("correctpassword")
        execute_db("INSERT INTO users (email, password_hash, role, status) VALUES ('student@bmsit.in', ?, 'student', 'active')", (pw_hash,), db_path=db_path)

    res_wrong_pw = client.post('/login', data={'email': 'student@bmsit.in', 'password': 'wrongpassword'}, follow_redirects=True)
    assert res_wrong_pw.status_code == 200
    assert b"Invalid email or password" in res_wrong_pw.data


def test_successful_student_authentication_and_session(client, app):
    """Verify authentic credentials log in, set session variables, and redirect."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw_hash = generate_password_hash("password123")
        uid = execute_db("INSERT INTO users (email, password_hash, role, status) VALUES ('benaka@bmsit.in', ?, 'student', 'active')", (pw_hash,), db_path=db_path)
        execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year) VALUES (?, 'Benaka Sham', 'CSE', '1st Year')", (uid,), db_path=db_path)

    response = client.post('/login', data={'email': 'benaka@bmsit.in', 'password': 'password123', 'remember': '1'}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/projects')

    # Verify session data
    with client.session_transaction() as sess:
        assert sess['user_id'] == uid
        assert sess['user_email'] == 'benaka@bmsit.in'
        assert sess['user_name'] == 'Benaka Sham'
        assert sess['user_role'] == 'student'
        assert sess.permanent is True


def test_protected_routes_require_authentication(client):
    """Verify unauthenticated requests to protected pages redirect to /login with next param."""
    # Profile edit is protected
    res_prof = client.get('/profile', follow_redirects=False)
    assert res_prof.status_code == 302
    assert '/login' in res_prof.headers['Location']
    assert 'next=%2Fprofile' in res_prof.headers['Location'] or 'next=/profile' in res_prof.headers['Location']

    # Project creation is protected
    res_proj = client.get('/projects/create', follow_redirects=False)
    assert res_proj.status_code == 302
    assert '/login' in res_proj.headers['Location']

    # Invitations management is protected
    res_inv = client.get('/invitations', follow_redirects=False)
    assert res_inv.status_code == 302
    assert '/login' in res_inv.headers['Location']


def test_logout_functionality(client, app):
    """Verify logout terminates session and redirects to /login."""
    with app.app_context():
        db_path = app.config['DATABASE']
        pw_hash = generate_password_hash("password123")
        uid = execute_db("INSERT INTO users (email, password_hash, role, status) VALUES ('testuser@bmsit.in', ?, 'student', 'active')", (pw_hash,), db_path=db_path)

    with client.session_transaction() as sess:
        sess['user_id'] = uid
        sess['user_email'] = 'testuser@bmsit.in'
        sess['user_name'] = 'Test User'

    res_logout = client.get('/logout', follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"You have been logged out." in res_logout.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_forgot_and_reset_password_workflow(client, app):
    """Verify the complete forgot password and reset password flow."""
    with app.app_context():
        db_path = app.config['DATABASE']
        old_pw = generate_password_hash("oldpassword123")
        uid = execute_db("INSERT INTO users (email, password_hash, role, status) VALUES ('resetme@bmsit.in', ?, 'student', 'active')", (old_pw,), db_path=db_path)

    # 1. Request password reset
    res_forgot = client.post('/forgot-password', data={'email': 'resetme@bmsit.in'}, follow_redirects=True)
    assert res_forgot.status_code == 200
    assert b"password reset instructions have been generated" in res_forgot.data
    assert b"/reset-password/" in res_forgot.data

    # Extract the token from the response HTML
    html = res_forgot.data.decode('utf-8')
    token_start = html.find('/reset-password/') + len('/reset-password/')
    token_end = html.find('"', token_start)
    token = html[token_start:token_end]
    assert len(token) > 10

    # 2. Open reset password form with token
    res_reset_page = client.get(f'/reset-password/{token}')
    assert res_reset_page.status_code == 200
    assert b"Create New Password" in res_reset_page.data

    # 3. Submit reset with non-matching passwords
    res_mismatch = client.post(f'/reset-password/{token}', data={'password': 'newpassword123', 'confirm_password': 'differentpassword'}, follow_redirects=True)
    assert b"Passwords do not match" in res_mismatch.data

    # 4. Submit reset with valid matching password
    res_success = client.post(f'/reset-password/{token}', data={'password': 'brandnewpassword123', 'confirm_password': 'brandnewpassword123'}, follow_redirects=True)
    assert res_success.status_code == 200
    assert b"Your password has been successfully reset" in res_success.data

    # 5. Verify database has updated password
    with app.app_context():
        user = query_db("SELECT password_hash FROM users WHERE id = ?", (uid,), one=True, db_path=db_path)
        assert check_password_hash(user['password_hash'], "brandnewpassword123") is True
        assert check_password_hash(user['password_hash'], "oldpassword123") is False

    # 6. Verify logging in with new password succeeds
    res_login_new = client.post('/login', data={'email': 'resetme@bmsit.in', 'password': 'brandnewpassword123'}, follow_redirects=False)
    assert res_login_new.status_code == 302
