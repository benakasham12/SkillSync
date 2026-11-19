"""
Unit tests verifying the SkillSync modern landing page and navigation routing.
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


def test_landing_page_renders_successfully(client):
    """Verify landing page at '/' renders status 200 and all essential copy."""
    response = client.get('/')
    assert response.status_code == 200
    html = response.data.decode('utf-8')

    # Hero section checks
    assert "Find Your Perfect Team" in html
    assert "Build Something Amazing" in html
    assert "Connect with talented students, discover complementary skills" in html
    assert "Find Your Team" in html
    assert "Explore How It Works" in html

    # Features checks
    assert "Smart Team Matching" in html
    assert "Skill-Based Profiles" in html
    assert "Project Collaboration" in html
    assert "Discover Opportunities" in html

    # How it works checks
    assert "Create Your Profile" in html
    assert "Discover Teammates" in html
    assert "Build Your Team" in html

    # Final CTA check
    assert "Your Next Great Project Starts With the Right Team." in html

    # Institutional & student attribution check
    assert "BMSIT&amp;M" in html or "BMSIT&M" in html
    assert "Harsh Tiwari" in html
    assert "Benaka Sham" in html
    assert "Goral Chhabra" in html
    assert "Akansha" in html

    # Verify complete removal of the hero preview mockup section
    assert "AI Healthcare Diagnostic Assistant" not in html
    assert "Priya Sharma" not in html
    assert "94.5" not in html
    assert "Zero Schedule Clashes" not in html
    assert "hero-preview-wrapper" not in html
    assert "mockup-candidate-card" not in html

    # Verify removal of college/department badges next to SkillSync logo and hero section
    navbar_and_hero = html.split('<footer')[0]
    assert "BMSIT&amp;M CSE 13" not in navbar_and_hero
    assert "brand-badge" not in html
    assert "Student Skill &amp; Project Team Finder &bull; BMSIT&amp;M IDT" not in html
    assert "Student Skill &amp; Project Team Finder" in html
    assert '<span class="brand-name">SkillSync</span>' in html


def test_projects_directory_route(client):
    """Verify '/projects' route continues to serve the projects directory."""
    response = client.get('/projects')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Projects" in html
