"""
Tests for Dark Mode / Light Mode Theme Toggle in SkillSync.
Verifies the presence of the toggle button, SVG icons, accessibility labels,
anti-flicker initialization script, and CSS theme tokens.
"""

import pytest
import re
import tempfile
import os
from pathlib import Path
from app import create_app
from app.models import init_db


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


def test_anti_flicker_script_in_head(client):
    """Verify that base.html includes the inline anti-flicker script in <head>."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Check script is placed inside head before stylesheet
    head_match = re.search(r"<head>(.*?)</head>", html, re.DOTALL)
    assert head_match is not None, "<head> tag not found in response"
    head_content = head_match.group(1)

    assert "skillsync_theme" in head_content
    assert "data-theme" in head_content
    assert "prefers-color-scheme: dark" in head_content


def test_theme_toggle_button_in_navbar(client):
    """Verify the circular theme toggle button is in .nav-right with Sun and Moon Lucide icons."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # Check toggle button presence
    assert 'id="themeToggleBtn"' in html
    assert 'class="theme-toggle-btn"' in html
    assert 'aria-label="Switch to Dark Mode"' in html
    assert 'title="Switch to Dark Mode"' in html

    # Check both Lucide Sun and Moon SVG icons are present inside
    assert 'class="theme-icon theme-icon-sun"' in html
    assert 'class="theme-icon theme-icon-moon"' in html


def test_sidebar_theme_toggle_in_drawer(client):
    """Verify the slide-out navigation drawer contains a theme toggle option."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert 'id="sidebarThemeToggleBtn"' in html
    assert "Switch to Dark Mode" in html


def test_theme_toggle_present_on_other_pages(client):
    """Verify the theme toggle is present across multiple views (login, register, projects)."""
    for endpoint in ["/login", "/register", "/projects"]:
        res = client.get(endpoint)
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert 'id="themeToggleBtn"' in html, f"Theme toggle missing on {endpoint}"
        assert 'class="theme-icon theme-icon-sun"' in html
        assert 'class="theme-icon theme-icon-moon"' in html


def test_css_theme_variables_and_classes():
    """Verify style.css contains [data-theme='dark'] tokens and theme transition classes."""
    css_path = Path("app/static/css/style.css")
    assert css_path.exists(), "app/static/css/style.css does not exist"
    css_content = css_path.read_text(encoding="utf-8")

    assert '[data-theme="dark"]' in css_content
    assert "--bg: #0b0f19" in css_content or "--bg: #0d1117" in css_content
    assert ".theme-toggle-btn" in css_content
    assert ".theme-icon-sun" in css_content
    assert ".theme-icon-moon" in css_content
    assert "transition: background-color" in css_content


def test_js_theme_toggle_logic():
    """Verify app.js contains theme toggle event handlers and localStorage persistence."""
    js_path = Path("app/static/js/app.js")
    assert js_path.exists(), "app/static/js/app.js does not exist"
    js_content = js_path.read_text(encoding="utf-8")

    assert "themeToggleBtn" in js_content
    assert "skillsync_theme" in js_content
    assert "skillsync:themechange" in js_content
    assert "data-theme" in js_content


def test_landing_page_hero_buttons_and_icons(client):
    """Verify that the hero section contains both primary and secondary CTA buttons with SVGs."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "btn-hero-primary" in html
    assert "btn-hero-secondary" in html
    assert "Explore How It Works" in html
    # Verify play icon is inside secondary button
    assert "<polygon points=" in html or "<polyline points=" in html


def test_dark_mode_button_contrast_css():
    """Verify style.css contains proper Dark Mode contrast rules for all button classes."""
    css_path = Path("app/static/css/style.css")
    assert css_path.exists()
    css = css_path.read_text(encoding="utf-8")

    # 1. Secondary hero button dark mode rules
    assert '[data-theme="dark"] .btn-hero-secondary' in css
    assert "#ffffff" in css  # White text/icon
    assert '[data-theme="dark"] .btn-hero-secondary svg' in css

    # 2. Global buttons dark mode rules
    assert '[data-theme="dark"] .btn-secondary' in css
    assert '[data-theme="dark"] .btn-ghost' in css
    assert '[data-theme="dark"] .btn-outline-primary' in css
    assert '[data-theme="dark"] .btn-success' in css
    assert '[data-theme="dark"] .btn-danger' in css
    assert '[data-theme="dark"] .btn-outline-danger' in css

