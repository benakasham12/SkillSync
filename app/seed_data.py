"""
Seed data loader for SkillSync.
Loads cohort taxonomy, students, and sample projects from app/seed_data.json
and populates the database cleanly and idempotently.
"""

import os
import json
from werkzeug.security import generate_password_hash
from app.models import get_db, init_db, query_db, execute_db

JSON_PATH = os.path.join(os.path.dirname(__file__), 'seed_data.json')


def load_seed_json():
    """Load JSON data from seed_data.json file."""
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_database(db_path=None):
    """Resets and seeds the database with initial catalog, users and demo projects from seed_data.json."""
    init_db(db_path)
    data = load_seed_json()

    conn = get_db(db_path)
    cur = conn.cursor()

    # Only clear tables if database has no existing projects, preserving user data
    existing_p_cnt = cur.execute("SELECT count(*) FROM projects").fetchone()[0]
    if existing_p_cnt == 0:
        cur.execute("DELETE FROM message_attachments")
        cur.execute("DELETE FROM message_read_status")
        cur.execute("DELETE FROM messages")
        cur.execute("DELETE FROM conversation_participants")
        cur.execute("DELETE FROM conversations")
        cur.execute("DELETE FROM reports")
        cur.execute("DELETE FROM invitations")
        cur.execute("DELETE FROM team_members")
        cur.execute("DELETE FROM project_availability_slots")
        cur.execute("DELETE FROM project_interests")
        cur.execute("DELETE FROM project_skill_requirements")
        cur.execute("DELETE FROM projects")
        cur.execute("DELETE FROM availability_slots")
        cur.execute("DELETE FROM student_interests")
        cur.execute("DELETE FROM student_skills")
        cur.execute("DELETE FROM student_profiles")
        cur.execute("DELETE FROM users")
        cur.execute("DELETE FROM audit_events")
        conn.commit()

    # 1. Seed Skills Catalog
    skills_to_insert = [(s['name'], s['category']) for s in data.get('skills_catalog', [])]
    cur.executemany("INSERT OR IGNORE INTO skills (name, category) VALUES (?, ?)", skills_to_insert)
    conn.commit()

    # 2. Seed Interests Catalog
    interests_to_insert = [(i['name'], i['category']) for i in data.get('interests_catalog', [])]
    cur.executemany("INSERT OR IGNORE INTO interests (name, category) VALUES (?, ?)", interests_to_insert)
    conn.commit()

    # Build skill and interest lookup maps
    skill_rows = cur.execute("SELECT id, name FROM skills").fetchall()
    skill_map = {r['name']: r['id'] for r in skill_rows}

    interest_rows = cur.execute("SELECT id, name FROM interests").fetchall()
    interest_map = {r['name']: r['id'] for r in interest_rows}

    # 3. Seed Admin / Faculty Account
    admin = data.get('admin_account', {})
    if admin:
        admin_pw = generate_password_hash(admin.get('password', 'admin123'))
        cur.execute("""
            INSERT OR IGNORE INTO users (email, password_hash, role, status)
            VALUES (?, ?, ?, 'active')
        """, (admin['email'], admin_pw, admin.get('role', 'admin')))
        conn.commit()

    # 4. Seed Student Accounts & Profiles
    default_pw = data.get('default_student_password', 'password123')
    hashed_pw = generate_password_hash(default_pw)
    user_id_map = {}

    for s in data.get('students', []):
        cur.execute("""
            INSERT OR IGNORE INTO users (email, password_hash, role, status)
            VALUES (?, ?, 'student', 'active')
        """, (s['email'], hashed_pw))
        conn.commit()

        user = cur.execute("SELECT id FROM users WHERE email = ?", (s['email'],)).fetchone()
        uid = user['id']
        user_id_map[s['email']] = uid

        cur.execute("""
            INSERT OR REPLACE INTO student_profiles 
            (user_id, display_name, usn, branch, year, section, institution, bio, github_url, linkedin_url, portfolio_url, visibility, is_match_ready)
            VALUES (?, ?, ?, ?, ?, ?, 'BMS Institute of Technology and Management', ?, ?, ?, ?, ?, 1)
        """, (
            uid, s['display_name'], s.get('usn'), s.get('branch', 'CSE'), s.get('year', '1st Year'), s.get('section', 'CSE-13'),
            s.get('bio'), s.get('github_url'), s.get('linkedin_url'), s.get('portfolio_url'), s.get('visibility', 'cohort_only')
        ))

        # Insert student skills
        for sk in s.get('skills', []):
            sk_name = sk['name']
            prof = sk.get('proficiency', 'intermediate')
            if sk_name in skill_map:
                cur.execute("""
                    INSERT OR REPLACE INTO student_skills (user_id, skill_id, proficiency, self_reported)
                    VALUES (?, ?, ?, 1)
                """, (uid, skill_map[sk_name], prof))

        # Insert student interests
        for int_name in s.get('interests', []):
            if int_name in interest_map:
                cur.execute("""
                    INSERT OR REPLACE INTO student_interests (user_id, interest_id)
                    VALUES (?, ?)
                """, (uid, interest_map[int_name]))

        # Insert student availability
        for slot in s.get('availability', []):
            cur.execute("""
                INSERT OR REPLACE INTO availability_slots (user_id, day_of_week, time_block)
                VALUES (?, ?, ?)
            """, (uid, slot['day'], slot['block']))

    conn.commit()

    # 5. Seed Sample Projects (only if database had no projects initially)
    if existing_p_cnt == 0:
        for p in data.get('projects', []):
            owner_id = user_id_map.get(p['owner_email'])
            if owner_id:
                # Infer appropriate category from interests or title
                category = p.get('category')
                if not category:
                    for int_name in p.get('interests', []):
                        if int_name in ['Web Development', 'App Development', 'AI / Machine Learning', 'Data Science', 'Cybersecurity', 'UI/UX Design', 'IoT & Hardware', 'Cloud Computing']:
                            category = int_name
                            break
                if not category:
                    category = 'Web Development' if 'Web' in p['title'] or 'SkillSync' in p['title'] else ('IoT & Hardware' if 'Sensor' in p['title'] else 'AI / Machine Learning')

                technologies = p.get('technologies', ', '.join([r['skill_name'] for r in p.get('requirements', [])[:4]]))
                duration = p.get('duration', '2–3 Months')
                collaboration_mode = p.get('collaboration_mode', 'Hybrid')
                availability = p.get('availability', 'Flexible')

                cur.execute("""
                    INSERT INTO projects (
                        owner_id, title, description, category, technologies, duration,
                        collaboration_mode, availability, course_context, team_size_min,
                        team_size_max, schedule_notes, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    owner_id, p['title'], p.get('description', ''),
                    category, technologies, duration,
                    collaboration_mode, availability,
                    p.get('course_context', 'Innovation & Design Thinking (IDT)'),
                    p.get('team_size_min', 2), p.get('team_size_max', 4),
                    p.get('schedule_notes', ''), p.get('status', 'published')
                ))
                proj_id = cur.lastrowid

                # Automatically register owner in team_members
                cur.execute("""
                    INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
                    VALUES (?, ?, 'owner', CURRENT_TIMESTAMP)
                """, (proj_id, owner_id))

                # Insert project skill requirements
                for req in p.get('requirements', []):
                    sk_name = req['skill_name']
                    if sk_name in skill_map:
                        cur.execute("""
                            INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight)
                            VALUES (?, ?, ?, ?)
                        """, (proj_id, skill_map[sk_name], req.get('priority', 'must-have'), req.get('weight', 3.0)))

                # Insert project availability slots
                for slot in p.get('availability_slots', []):
                    cur.execute("""
                        INSERT INTO project_availability_slots (project_id, day_of_week, time_block)
                        VALUES (?, ?, ?)
                    """, (proj_id, slot['day'], slot['block']))

                # Insert project interests
                for int_name in p.get('interests', []):
                    if int_name in interest_map:
                        cur.execute("""
                            INSERT INTO project_interests (project_id, interest_id)
                            VALUES (?, ?)
                        """, (proj_id, interest_map[int_name]))

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded from app/seed_data.json.")
