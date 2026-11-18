"""
Automated unit tests for PRD Section 6 Matching Logic and Worked Example (Section 6.3).
"""

import pytest
import tempfile
import os
from app.models import init_db, execute_db, query_db
from app.matching import calculate_matches_for_project
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


def test_worked_example_section_6_3(test_db):
    """
    Direct verification of PRD Section 6.3 Worked Example:
    - Project requires: Python (weight 3), UI/UX (weight 2), Presentation (weight 1). Total weight = 6.
    - Candidate reports: Python and Presentation (weights 3 + 1 = 4).
      Skill fit = 4 / 6 * 100 = 66.666... -> 66.7%
    - Availability: 80% overlap (e.g. candidate has 4 of 5 project slots).
    - Interest: 50% overlap (e.g. candidate shares 1 of 2 project interest tags).
    - Expected score = 0.65 * 66.7 + 0.25 * 80 + 0.10 * 50 = 43.355 + 20.0 + 5.0 = 68.355 -> 68.4 or 68.3%
    - Must report UI/UX as missing requirement!
    """
    pw = generate_password_hash("pass")

    # 1. Insert Skills
    s_python = execute_db("INSERT INTO skills (name, category) VALUES ('Python', 'Backend')", db_path=test_db)
    s_uiux = execute_db("INSERT INTO skills (name, category) VALUES ('UI/UX', 'Design')", db_path=test_db)
    s_pres = execute_db("INSERT INTO skills (name, category) VALUES ('Presentation', 'Soft Skills')", db_path=test_db)

    # 2. Insert Interests
    int_web = execute_db("INSERT INTO interests (name, category) VALUES ('Web Dev', 'Tech')", db_path=test_db)
    int_ai = execute_db("INSERT INTO interests (name, category) VALUES ('AI', 'Tech')", db_path=test_db)

    # 3. Create Project Owner
    owner_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('owner@bmsit.in', ?, 'student')", (pw,), db_path=test_db)
    execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready) VALUES (?, 'Owner', 'CSE', '1st Year', 1)", (owner_id,), db_path=test_db)

    # 4. Create Project
    proj_id = execute_db("""
        INSERT INTO projects (owner_id, title, status, team_size_min, team_size_max)
        VALUES (?, 'IDT Test Project', 'published', 2, 4)
    """, (owner_id,), db_path=test_db)

    # Add Requirements: Python (wt 3), UI/UX (wt 2), Presentation (wt 1)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (proj_id, s_python), db_path=test_db)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 2.0)", (proj_id, s_uiux), db_path=test_db)
    execute_db("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'preferred', 1.0)", (proj_id, s_pres), db_path=test_db)

    # Add 5 Project Availability Slots
    slots = [
        ('Monday', 'Morning (9AM-12PM)'),
        ('Tuesday', 'Morning (9AM-12PM)'),
        ('Wednesday', 'Morning (9AM-12PM)'),
        ('Thursday', 'Morning (9AM-12PM)'),
        ('Friday', 'Morning (9AM-12PM)')
    ]
    for day, block in slots:
        execute_db("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, ?, ?)", (proj_id, day, block), db_path=test_db)

    # Add 2 Project Interests: Web Dev and AI
    execute_db("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (proj_id, int_web), db_path=test_db)
    execute_db("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (proj_id, int_ai), db_path=test_db)

    # 5. Create Candidate
    cand_id = execute_db("INSERT INTO users (email, password_hash, role) VALUES ('candidate@bmsit.in', ?, 'student')", (pw,), db_path=test_db)
    execute_db("INSERT INTO student_profiles (user_id, display_name, branch, year, is_match_ready, visibility) VALUES (?, 'Candidate', 'CSE', '1st Year', 1, 'public')", (cand_id,), db_path=test_db)

    # Candidate has Python and Presentation
    execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'advanced')", (cand_id, s_python), db_path=test_db)
    execute_db("INSERT INTO student_skills (user_id, skill_id, proficiency) VALUES (?, ?, 'intermediate')", (cand_id, s_pres), db_path=test_db)

    # Candidate has 4 of 5 slots (80% availability)
    for day, block in slots[:4]:
        execute_db("INSERT INTO availability_slots (user_id, day_of_week, time_block) VALUES (?, ?, ?)", (cand_id, day, block), db_path=test_db)

    # Candidate has 1 of 2 interests: Web Dev (50% interest fit)
    execute_db("INSERT INTO student_interests (user_id, interest_id) VALUES (?, ?)", (cand_id, int_web), db_path=test_db)

    # Calculate match
    candidates = calculate_matches_for_project(proj_id, db_path=test_db)

    assert len(candidates) == 1
    c = candidates[0]

    # Verify Skill Fit: (3 + 1) / 6 = 66.7%
    assert abs(c['skill_fit'] - 66.7) < 0.1

    # Verify Availability Fit: 4 / 5 = 80.0%
    assert c['availability_fit'] == 80.0

    # Verify Interest Fit: 1 / 2 = 50.0%
    assert c['interest_fit'] == 50.0

    # Verify Total Score: approx 68.3 or 68.4
    assert 68.2 <= c['match_score'] <= 68.5

    # Verify UI/UX is flagged as missing requirement!
    assert 'UI/UX' in c['missing_must_haves']
    assert len(c['matched_skills']) == 2
