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

    # Verify complete removal of the Introduction to SkillSync section from homepage per instructions
    assert '<h2 class="section-title">Introduction to SkillSync</h2>' not in html
    assert "A Better Way to Build" not in html
    assert "home-intro-section" not in html
    assert "hero-horizon-line" not in html

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
    # Verify complete removal of hero pill banner "Student Skill & Project Team Finder"
    assert "Student Skill &amp; Project Team Finder" not in html
    assert "hero-badge" not in html
    assert "badge-pulsing-dot" not in html
    assert '<span class="brand-name">SkillSync</span>' in html


def test_projects_directory_route(client):
    """Verify '/projects' route continues to serve the projects directory."""
    response = client.get('/projects')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    assert "Projects" in html


def test_beams_background_only_on_homepage(client):
    """Verify that BeamsBackground canvas is strictly on the homepage hero and NOT on other pages."""
    # 1. Homepage has the beams canvas
    home_res = client.get('/')
    assert home_res.status_code == 200
    home_html = home_res.data.decode('utf-8')
    assert 'id="beamsBackgroundCanvas"' in home_html
    assert 'beams-background-wrapper' in home_html

    # 2. Other pages MUST NOT have the beams canvas (Scope Restrictions)
    for path in ['/login', '/register', '/projects']:
        res = client.get(path)
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        assert 'id="beamsBackgroundCanvas"' not in html
        assert 'beams-background-wrapper' not in html


def test_beams_background_react_component_file():
    """Verify the /components/ui/beams-background.tsx React component exists and is valid."""
    from pathlib import Path
    comp_path = Path("components/ui/beams-background.tsx")
    assert comp_path.exists(), "components/ui/beams-background.tsx not found"
    code = comp_path.read_text(encoding="utf-8")

    assert "export function BeamsBackground" in code
    assert "createBeam" in code
    assert "children" in code
    assert "cancelAnimationFrame" in code
    assert "prefers-reduced-motion" in code


def test_about_section_markup_and_cards(client):
    """Verify the About section renders team member cards, institution card, and problem/solution story cards."""
    res = client.get('/')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Card containers
    assert 'about-section' in html
    assert 'about-grid' in html
    assert 'about-story-card' in html
    assert 'The Problem We Are Solving' in html
    assert 'Our Engineering Solution' in html
    assert 'institution-card' in html
    assert 'BMS Institute of Technology &amp; Management' in html
    assert 'team-cards-grid' in html

    # All 4 team members
    assert 'Harsh Tiwari' in html
    assert 'Benaka Sham' in html
    assert 'Goral Chhabra' in html
    assert 'Akansha' in html
    assert 'member-card' in html
    assert 'member-name' in html
    assert 'member-role' in html
    assert 'CSE &bull; Section 13' in html
    assert 'academic-note' in html


def test_css_about_section_visibility_and_alignment():
    """Verify CSS has readable dark navy (#111827) names, slate grey roles (#64748B), white card backgrounds, and responsive container padding."""
    from pathlib import Path
    css_path = Path("app/static/css/style.css")
    assert css_path.exists()
    css = css_path.read_text(encoding="utf-8")

    # Team member names dark navy (#111827)
    assert "#111827" in css

    # Department and section details slate grey (#64748B)
    assert "#64748B" in css

    # Team member cards have white background and proper borders
    assert ".member-card" in css
    assert ".member-avatar" in css

    # Story cards have dark heading and readable text
    assert ".story-heading" in css
    assert ".story-text" in css

    # Landing container responsive padding (px-4, px-6, lg:px-8 equivalents: 1rem, 1.5rem, 2rem)
    assert ".landing-container" in css
    assert "padding-left: 2rem" in css or "padding: 0 2rem" in css or "padding: 0 1.5rem" in css

    # Dark mode overrides ensure proper contrast and no white-on-white text
    assert '[data-theme="dark"] .member-card' in css
    assert '[data-theme="dark"] .about-story-card' in css
    assert '[data-theme="dark"] .institution-card' in css


def test_dedicated_multi_page_routes_and_navigation(client):
    """Verify all major sections have dedicated independent pages with direct header navigation."""
    pages = [
        ('/', 'Home'),
        ('/about-skillsync', 'Introduction'),
        ('/projects', 'Find Projects'),
        ('/students', 'Explore Students'),
        ('/features', 'Features'),
        ('/how-it-works', 'How It Works'),
        ('/about', 'About Us'),
        ('/contact', 'Contact')
    ]

    for url, label in pages:
        res = client.get(url)
        assert res.status_code == 200, f"Page {url} failed with {res.status_code}"
        html = res.data.decode('utf-8')

        # Header contains all direct navigation links on desktop without More dropdown
        assert 'href="/"' in html
        assert 'href="/about-skillsync"' in html
        assert 'href="/projects"' in html
        assert 'href="/students"' in html
        assert 'href="/features"' in html
        assert 'href="/how-it-works"' in html
        assert 'href="/about"' in html
        assert 'href="/contact"' in html
        assert 'nav-menu-links' in html
        assert 'more-dropdown' not in html

        # Active link highlight
        assert 'nav-menu-link' in html
        assert 'active' in html


def test_about_skillsync_dedicated_page(client):
    """Verify the dedicated '/about-skillsync' page renders all Introduction section content."""
    res = client.get('/about-skillsync')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Core headers and description
    assert "A Better Way to Build" in html
    assert "Introduction to SkillSync" in html
    assert "SkillSync is an engineering platform that replaces chaotic student group chats" in html

    # All 4 core pillar cards
    assert "Smart Team Matching" in html
    assert "Skill-Based Profiles" in html
    assert "Project Collaboration" in html
    assert "Discover Opportunities" in html
    assert "Deterministic 65/25/10 scoring" in html

    # Check active state in navigation
    assert 'class="nav-menu-link active">Introduction</a>' in html


def test_dedicated_pages_content(client):
    """Verify each dedicated page displays its specialized content."""
    # 1. Features
    res = client.get('/features')
    html = res.data.decode('utf-8')
    assert "Designed for Modern Engineering Projects" in html
    assert "Deterministic Matching Engine" in html
    assert "65%" in html
    assert "25%" in html
    assert "10%" in html

    # 2. How It Works
    res = client.get('/how-it-works')
    html = res.data.decode('utf-8')
    assert "How SkillSync Works" in html
    assert "Create Your Profile" in html
    assert "Discover Teammates" in html
    assert "Build Your Team" in html
    assert "Frequently Asked Questions" in html

    # 3. About Us
    res = client.get('/about')
    html = res.data.decode('utf-8')
    assert "The Problem We Are Solving" in html
    assert "Our Engineering Solution" in html
    assert "BMS Institute of Technology &amp; Management" in html or "BMSIT&amp;M" in html
    assert "Harsh Tiwari" in html
    assert "Benaka Sham" in html

    # 4. Contact
    res = client.get('/contact')
    html = res.data.decode('utf-8')
    assert "Get in Touch with SkillSync" in html
    assert "Send Us a Message" in html
    assert "Campus Location" in html

    # 5. Contact Form Submission
    post_res = client.post('/contact', data={
        'name': 'Test Student',
        'email': 'student@bmsit.in',
        'subject': 'General Question',
        'message': 'Testing multi-page contact form dispatch.'
    }, follow_redirects=True)
    assert post_res.status_code == 200
    assert "Thank you for reaching out" in post_res.data.decode('utf-8')

    # 6. Students Directory
    res = client.get('/students')
    html = res.data.decode('utf-8')
    assert "Explore Talented Engineering Students" in html
    assert "directory-search-input" in html



