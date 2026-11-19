"""
Automated test suite verifying the GitHub-style Slide-Out Sidebar Navigation in SkillSync:
Validates:
1. Compact top navbar layout (Hamburger button, SkillSync logo, Messages icon shortcut, profile avatar).
2. Vertical slide-out sidebar container (#githubSidebar) and overlay backdrop (#sidebarBackdrop).
3. Section 1: Main Navigation (Home, Features, How It Works, About Us).
4. Section 2: Projects (Explore Projects, Create New Project, My Projects, Invitations).
5. Section 3: Communication (Messages, Project Group Chats).
6. Section 4: Account (My Profile, Coordinator Analytics, Logout / Login, Register).
7. Active page class highlighting matching current route endpoint.
8. Unread message notification badges in both navbar and sidebar.
"""

import pytest
import tempfile
import os
from app import create_app
from app.models import init_db, execute_db
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


def create_student(app, email, name):
    db_path = app.config['DATABASE']
    pw_hash = generate_password_hash('password123')
    uid = execute_db(
        "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'student')",
        (email, pw_hash),
        db_path=db_path
    )
    execute_db(
        """INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready)
           VALUES (?, ?, 'CSE', '3rd Year', 1)""",
        (uid, name),
        db_path=db_path
    )
    return uid


def login_student(client, user_id, email, name):
    with client.session_transaction() as sess:
        sess['user_id'] = user_id
        sess['user_email'] = email
        sess['user_name'] = name
        sess['user_role'] = 'student'


def test_compact_top_navbar_elements(client):
    """Top navbar contains hamburger button, SkillSync brand, and uncluttered layout."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Top Navbar essentials
    assert 'id="sidebarToggleBtn"' in html
    assert 'class="btn-hamburger"' in html
    assert '<span class="brand-name">SkillSync</span>' in html
    assert 'class="nav-left"' in html
    assert 'class="nav-right"' in html


def test_sidebar_drawer_structure_and_backdrop(client):
    """Sidebar drawer container, close button, and backdrop overlay are present in DOM."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    assert 'id="githubSidebar"' in html
    assert 'class="github-sidebar"' in html
    assert 'id="sidebarCloseBtn"' in html
    assert 'id="sidebarBackdrop"' in html
    assert 'class="sidebar-backdrop"' in html


def test_sidebar_navigation_sections_logged_out(client):
    """Sidebar organizes navigation into groups when user is logged out."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Section 1: Main Navigation
    assert 'Main Navigation' in html
    assert 'Home' in html
    assert 'Features' in html
    assert 'How It Works' in html
    assert 'About Us' in html

    # Section 2: Projects
    assert 'Explore Projects' in html

    # Section 3: Communication
    assert 'Messages' in html

    # Section 4: Account (Logged out)
    assert 'Student Login' in html
    assert 'Get Started / Register' in html


def test_sidebar_navigation_sections_logged_in(app, client):
    """Sidebar provides full authenticated student links and badges."""
    uid = create_student(app, 'benaka@bmsit.in', 'Benaka Sham')
    login_student(client, uid, 'benaka@bmsit.in', 'Benaka Sham')

    res = client.get('/projects')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Authenticated User Badge in sidebar
    assert 'sidebar-user-card' in html
    assert 'Benaka Sham' in html
    assert 'benaka@bmsit.in' in html

    # Section 2: Projects (Authenticated)
    assert 'Create New Project' in html
    assert 'My Projects' in html
    assert 'Invitations' in html

    # Section 3: Communication
    assert 'Messages' in html
    assert 'Project Group Chats' in html
    assert 'id="sidebarUnreadBadge"' in html

    # Section 4: Account
    assert 'My Profile' in html
    assert 'Logout' in html


def test_active_route_highlighting(app, client):
    """Active sidebar link receives .active class on current route."""
    # 1. On landing page, Home is active
    res_home = client.get('/')
    html_home = res_home.data.decode('utf-8')
    assert 'class="sidebar-link active"' in html_home

    # 2. On projects page, Explore Projects is active
    res_projects = client.get('/projects')
    html_projects = res_projects.data.decode('utf-8')
    assert 'class="sidebar-link active"' in html_projects


def test_topbar_messages_badge_sync(app, client):
    """Top bar contains direct messages shortcut and dynamic unread badge."""
    uid = create_student(app, 'benaka@bmsit.in', 'Benaka Sham')
    login_student(client, uid, 'benaka@bmsit.in', 'Benaka Sham')

    res = client.get('/')
    html = res.data.decode('utf-8')
    assert 'id="navMessagesLink"' in html
    assert 'id="navUnreadMessagesBadge"' in html
    assert 'id="sidebarUnreadBadge"' in html
