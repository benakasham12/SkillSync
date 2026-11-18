"""
Automated unit tests for PRD FR-11: Team Roster and Skill Coverage.
"""

import pytest
import tempfile
import os
from app.models import init_db, execute_db
from app.matching import compute_team_skill_coverage
from werkzeug.security import generate_password_hash


@pytest.fixture
def test_db():
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    init_db(path)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def test_team_coverage_and_gap_filling(test_db):
    """
    Tests that:
    1. Initially, owner only covers skills they possess.
    2. When new members join, coverage percentage increases.
    3. All must-haves covered flag activates only when 100% must-haves are covered.
    """
    pw = generate_password_hash("pass")

    s1 = execute_db("INSERT INTO skills (name, category) VALUES ('Flask', 'Backend')", db_path=test_db)
    s2 = execute_db("INSERT INTO skills (name, category) VALUES ('Figma', 'Design')", db_path=test_db)
    s3 = execute_db("INSERT INTO skills (name, category) VALUES ('Testing', 'QA')", db_path=test_db)

    # Owner has Flask only
    owner_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('benaka@bmsit.in', ?)", (pw,), db_path=test_db)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Benaka')", (owner_id,), db_path=test_db)
    execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (owner_id, s1), db_path=test_db)

    proj_id = execute_db("INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max) VALUES (?, 'SkillSync', 'published', 2, 3)", (owner_id,), db_path=test_db)

    # Add requirements: Flask (must-have), Figma (must-have), Testing (preferred)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s1), db_path=test_db)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s2), db_path=test_db)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'preferred', 1.0)", (proj_id, s3), db_path=test_db)

    # Step 1: Initial Coverage (Owner only)
    cov1 = compute_team_skill_coverage(proj_id, db_path=test_db)
    assert cov1['current_team_size'] == 1
    assert cov1['must_have_count'] == 2
    assert cov1['must_have_covered'] == 1 # Only Flask is covered
    assert cov1['must_have_coverage_pct'] == 50.0
    assert not cov1['all_must_haves_covered']

    # Step 2: Member 2 (Goral) joins with Figma
    mem2_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('goral@bmsit.in', ?)", (pw,), db_path=test_db)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Goral')", (mem2_id,), db_path=test_db)
    execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (mem2_id, s2), db_path=test_db)
    execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'member')", (proj_id, mem2_id), db_path=test_db)

    cov2 = compute_team_skill_coverage(proj_id, db_path=test_db)
    assert cov2['current_team_size'] == 2
    assert cov2['must_have_covered'] == 2 # Flask & Figma both covered!
    assert cov2['must_have_coverage_pct'] == 100.0
    assert cov2['all_must_haves_covered'] is True
    assert cov2['total_covered'] == 2
    assert cov2['total_requirements'] == 3
    assert not cov2['is_team_full']

    # Step 3: Member 3 joins (reaches max capacity 3)
    mem3_id = execute_db("INSERT INTO users (email, password_hash) VALUES ('akansha@bmsit.in', ?)", (pw,), db_path=test_db)
    execute_db("INSERT INTO student_profiles (user_id, display_name) VALUES (?, 'Akansha')", (mem3_id,), db_path=test_db)
    execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (mem3_id, s3), db_path=test_db)
    execute_db("INSERT INTO team_members (project_id, user_id, role) VALUES (?, ?, 'member')", (proj_id, mem3_id), db_path=test_db)

    cov3 = compute_team_skill_coverage(proj_id, db_path=test_db)
    assert cov3['current_team_size'] == 3
    assert cov3['is_team_full'] is True
    assert cov3['total_covered'] == 3
    assert cov3['overall_coverage_pct'] == 100.0
