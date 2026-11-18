"""
Seed data populated with BMSIT&M CSE 13 cohort members, skills taxonomy,
interests, sample course projects and realistic availability schedules.
"""

from werkzeug.security import generate_password_hash
from app.models import get_db, init_db, query_db, execute_db

DEFAULT_PASSWORD = "password123"

SKILLS_CATALOG = [
    # Frontend
    ("HTML/CSS/JavaScript", "Frontend"),
    ("React", "Frontend"),
    ("Tailwind CSS", "Frontend"),
    ("Vue.js", "Frontend"),
    # Backend
    ("Python", "Backend"),
    ("Flask", "Backend"),
    ("Node.js/Express", "Backend"),
    ("Java/Spring Boot", "Backend"),
    ("REST API Design", "Backend"),
    # Database
    ("Database Modeling", "Database"),
    ("SQLite/PostgreSQL", "Database"),
    ("MongoDB", "Database"),
    # Design & UI/UX
    ("UI/UX", "Design"),
    ("Figma", "Design"),
    ("Wireframing & Prototyping", "Design"),
    # Data & AI
    ("Machine Learning", "Data/AI"),
    ("Data Analysis/Pandas", "Data/AI"),
    ("Prompt Engineering", "Data/AI"),
    # Tools & DevOps
    ("Git/GitHub", "Tools"),
    ("Docker", "Tools"),
    ("Testing/QA", "Tools"),
    # Soft skills & Presentation
    ("Presentation", "Soft Skills"),
    ("Project Management", "Soft Skills"),
    ("Technical Writing", "Soft Skills"),
    ("IoT & Hardware", "Tools")
]

INTERESTS_CATALOG = [
    ("Web Development", "Technology"),
    ("Artificial Intelligence", "Technology"),
    ("Design & Creative", "Design"),
    ("Mobile Applications", "Technology"),
    ("IoT & Hardware", "Hardware"),
    ("Open Source Software", "Community"),
    ("Social Impact", "Mission"),
    ("FinTech", "Domain"),
    ("EdTech & Learning", "Domain"),
    ("Healthcare Tech", "Domain")
]

TIME_BLOCKS = [
    "Morning (9AM-12PM)",
    "Afternoon (1PM-4PM)",
    "Evening (5PM-8PM)",
    "Night (8PM-11PM)"
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

SAMPLE_STUDENTS = [
    {
        "email": "benaka@bmsit.in",
        "display_name": "Benaka Sham",
        "usn": "1BY26CS013",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Full-stack developer focused on Python/Flask and robust data modeling. Passionate about requirement-first architectures.",
        "github_url": "https://github.com/benakasham",
        "linkedin_url": "https://linkedin.com/in/benakasham",
        "portfolio_url": "https://benakasham.dev",
        "visibility": "public",
        "skills": [
            ("Python", "advanced"),
            ("Flask", "advanced"),
            ("Database Modeling", "intermediate"),
            ("REST API Design", "advanced"),
            ("Git/GitHub", "advanced")
        ],
        "interests": ["Web Development", "Artificial Intelligence", "EdTech & Learning"],
        "availability": [
            ("Monday", "Evening (5PM-8PM)"),
            ("Wednesday", "Evening (5PM-8PM)"),
            ("Friday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)"),
            ("Saturday", "Afternoon (1PM-4PM)")
        ]
    },
    {
        "email": "harsh@bmsit.in",
        "display_name": "Harsh Tiwari",
        "usn": "1BY26CS028",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Backend engineer & ML enthusiast. Love writing fast APIs and training applied computer vision models.",
        "github_url": "https://github.com/harshtiwari",
        "linkedin_url": "https://linkedin.com/in/harshtiwari",
        "portfolio_url": None,
        "visibility": "cohort_only",
        "skills": [
            ("Python", "advanced"),
            ("Machine Learning", "intermediate"),
            ("Data Analysis/Pandas", "intermediate"),
            ("SQLite/PostgreSQL", "intermediate"),
            ("Git/GitHub", "intermediate")
        ],
        "interests": ["Artificial Intelligence", "Web Development", "Social Impact"],
        "availability": [
            ("Tuesday", "Evening (5PM-8PM)"),
            ("Thursday", "Evening (5PM-8PM)"),
            ("Saturday", "Afternoon (1PM-4PM)"),
            ("Sunday", "Morning (9AM-12PM)")
        ]
    },
    {
        "email": "goral@bmsit.in",
        "display_name": "Goral Chhabra",
        "usn": "1BY26CS025",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "UI/UX Designer and Frontend creator. Obsessed with intuitive interaction design, wireframes, and design systems in Figma.",
        "github_url": "https://github.com/goralchhabra",
        "linkedin_url": "https://linkedin.com/in/goralchhabra",
        "portfolio_url": "https://goral.design",
        "visibility": "public",
        "skills": [
            ("UI/UX", "advanced"),
            ("Figma", "advanced"),
            ("Wireframing & Prototyping", "advanced"),
            ("HTML/CSS/JavaScript", "intermediate"),
            ("Tailwind CSS", "intermediate")
        ],
        "interests": ["Design & Creative", "Web Development", "EdTech & Learning"],
        "availability": [
            ("Monday", "Evening (5PM-8PM)"),
            ("Wednesday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)"),
            ("Saturday", "Afternoon (1PM-4PM)")
        ]
    },
    {
        "email": "akansha@bmsit.in",
        "display_name": "Akansha",
        "usn": "1BY26CS005",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "QA engineer and technical writer. Specializing in test automation, relational databases and project documentation.",
        "github_url": "https://github.com/akansha-cs",
        "linkedin_url": "https://linkedin.com/in/akansha",
        "portfolio_url": None,
        "visibility": "public",
        "skills": [
            ("Testing/QA", "advanced"),
            ("SQLite/PostgreSQL", "advanced"),
            ("Technical Writing", "advanced"),
            ("Presentation", "intermediate"),
            ("Git/GitHub", "intermediate")
        ],
        "interests": ["EdTech & Learning", "Open Source Software", "Social Impact"],
        "availability": [
            ("Monday", "Evening (5PM-8PM)"),
            ("Friday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)"),
            ("Sunday", "Afternoon (1PM-4PM)")
        ]
    },
    {
        "email": "priya@bmsit.in",
        "display_name": "Priya Sharma",
        "usn": "1BY26CS052",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Product manager and pitch enthusiast. Experience pitching IDT projects, creating slide decks and user research.",
        "github_url": None,
        "linkedin_url": "https://linkedin.com/in/priyasharma",
        "portfolio_url": None,
        "visibility": "public",
        "skills": [
            ("Presentation", "advanced"),
            ("Project Management", "advanced"),
            ("UI/UX", "intermediate"),
            ("Wireframing & Prototyping", "intermediate")
        ],
        "interests": ["Design & Creative", "EdTech & Learning", "Social Impact"],
        "availability": [
            ("Wednesday", "Evening (5PM-8PM)"),
            ("Thursday", "Evening (5PM-8PM)"),
            ("Saturday", "Afternoon (1PM-4PM)"),
            ("Sunday", "Morning (9AM-12PM)")
        ]
    },
    {
        "email": "rohan@bmsit.in",
        "display_name": "Rohan Kulkarni",
        "usn": "1BY26CS064",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Hardware, IoT, and embedded firmware developer. Building smart campus sensors and microcontroller integrations.",
        "github_url": "https://github.com/rohankulkarni",
        "linkedin_url": "https://linkedin.com/in/rohankulkarni",
        "portfolio_url": None,
        "visibility": "cohort_only",
        "skills": [
            ("IoT & Hardware", "advanced"),
            ("Python", "intermediate"),
            ("REST API Design", "intermediate"),
            ("Git/GitHub", "intermediate")
        ],
        "interests": ["IoT & Hardware", "Healthcare Tech", "Open Source Software"],
        "availability": [
            ("Monday", "Evening (5PM-8PM)"),
            ("Tuesday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)")
        ]
    },
    {
        "email": "ananya@bmsit.in",
        "display_name": "Ananya Rao",
        "usn": "1BY26CS010",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Data analyst passionate about statistics, data cleaning, and compelling visualizations in Python and SQL.",
        "github_url": "https://github.com/ananyarao",
        "linkedin_url": "https://linkedin.com/in/ananyarao",
        "portfolio_url": None,
        "visibility": "public",
        "skills": [
            ("Data Analysis/Pandas", "advanced"),
            ("SQLite/PostgreSQL", "intermediate"),
            ("Python", "intermediate"),
            ("Presentation", "intermediate")
        ],
        "interests": ["Artificial Intelligence", "Healthcare Tech", "Social Impact"],
        "availability": [
            ("Wednesday", "Evening (5PM-8PM)"),
            ("Friday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)"),
            ("Sunday", "Morning (9AM-12PM)")
        ]
    },
    {
        "email": "rahul@bmsit.in",
        "display_name": "Rahul Verma",
        "usn": "1BY26CS058",
        "branch": "CSE",
        "year": "1st Year",
        "section": "CSE-13",
        "bio": "Frontend developer building responsive SPAs with React, Tailwind CSS, and state management.",
        "github_url": "https://github.com/rahulverma",
        "linkedin_url": "https://linkedin.com/in/rahulverma",
        "portfolio_url": None,
        "visibility": "public",
        "skills": [
            ("React", "advanced"),
            ("Tailwind CSS", "advanced"),
            ("HTML/CSS/JavaScript", "advanced"),
            ("Git/GitHub", "intermediate")
        ],
        "interests": ["Web Development", "Open Source Software", "Design & Creative"],
        "availability": [
            ("Monday", "Evening (5PM-8PM)"),
            ("Thursday", "Evening (5PM-8PM)"),
            ("Saturday", "Morning (9AM-12PM)"),
            ("Saturday", "Afternoon (1PM-4PM)")
        ]
    }
]


def seed_database(db_path=None):
    """Resets and seeds the database with initial catalog, users and demo projects."""
    init_db(db_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    # Clear existing demo projects and relations to ensure clean idempotency
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
    cur.executemany("INSERT OR IGNORE INTO skills (name, category) VALUES (?, ?)", SKILLS_CATALOG)
    conn.commit()

    # 2. Seed Interests Catalog
    cur.executemany("INSERT OR IGNORE INTO interests (name, category) VALUES (?, ?)", INTERESTS_CATALOG)
    conn.commit()

    # Build skill and interest lookup maps
    skill_rows = cur.execute("SELECT id, name FROM skills").fetchall()
    skill_map = {r['name']: r['id'] for r in skill_rows}

    interest_rows = cur.execute("SELECT id, name FROM interests").fetchall()
    interest_map = {r['name']: r['id'] for r in interest_rows}

    # 3. Seed Admin / Faculty Account
    admin_pw = generate_password_hash("admin123")
    cur.execute("""
        INSERT OR IGNORE INTO users (email, password_hash, role, status)
        VALUES ('faculty@bmsit.in', ?, 'admin', 'active')
    """, (admin_pw,))
    conn.commit()

    # 4. Seed Student Accounts & Profiles
    hashed_pw = generate_password_hash(DEFAULT_PASSWORD)
    user_id_map = {}

    for s in SAMPLE_STUDENTS:
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
            uid, s['display_name'], s['usn'], s['branch'], s['year'], s['section'],
            s['bio'], s['github_url'], s['linkedin_url'], s['portfolio_url'], s['visibility']
        ))

        # Insert student skills
        for sk_name, prof in s['skills']:
            if sk_name in skill_map:
                cur.execute("""
                    INSERT OR REPLACE INTO student_skills (user_id, skill_id, proficiency, self_reported)
                    VALUES (?, ?, ?, 1)
                """, (uid, skill_map[sk_name], prof))

        # Insert student interests
        for int_name in s['interests']:
            if int_name in interest_map:
                cur.execute("""
                    INSERT OR REPLACE INTO student_interests (user_id, interest_id)
                    VALUES (?, ?)
                """, (uid, interest_map[int_name]))

        # Insert student availability
        for day, block in s['availability']:
            cur.execute("""
                INSERT OR REPLACE INTO availability_slots (user_id, day_of_week, time_block)
                VALUES (?, ?, ?)
            """, (uid, day, block))

    conn.commit()

    # 5. Seed Sample Projects
    # Project 1: IDT Team Finder (owned by Benaka Sham)
    benaka_id = user_id_map.get("benaka@bmsit.in")
    if benaka_id:
        cur.execute("""
            INSERT INTO projects (owner_id, title, description, course_context, team_size_min, team_size_max, schedule_notes, status)
            VALUES (?, 'Student Skill & Project Team Finder (SkillSync)', 
                    'An Innovation & Design Thinking platform that matches classmates through complementary skills, availability and shared interests before committing to teams.',
                    'Innovation & Design Thinking (IDT)', 3, 4, 
                    'Looking to collaborate on weekday evenings and Saturday mornings.', 'published')
        """, (benaka_id,))
        p1_id = cur.lastrowid

        # Requirements: Python (weight 3), UI/UX (weight 2), Presentation (weight 1), Testing/QA (weight 2)
        # Exactly matches the worked example in PRD Section 6.3!
        reqs = [
            ("Python", "must-have", 3.0),
            ("UI/UX", "must-have", 2.0),
            ("Presentation", "preferred", 1.0),
            ("Testing/QA", "preferred", 2.0)
        ]
        for sk_name, prio, wt in reqs:
            if sk_name in skill_map:
                cur.execute("""
                    INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight)
                    VALUES (?, ?, ?, ?)
                """, (p1_id, skill_map[sk_name], prio, wt))

        # Project desired schedule
        cur.execute("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, 'Monday', 'Evening (5PM-8PM)')", (p1_id,))
        cur.execute("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, 'Wednesday', 'Evening (5PM-8PM)')", (p1_id,))
        cur.execute("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, 'Saturday', 'Morning (9AM-12PM)')", (p1_id,))

        # Project interests
        if "Web Development" in interest_map:
            cur.execute("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (p1_id, interest_map["Web Development"]))
        if "EdTech & Learning" in interest_map:
            cur.execute("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (p1_id, interest_map["EdTech & Learning"]))

    # Project 2: Smart Campus Navigation (owned by Rohan Kulkarni)
    rohan_id = user_id_map.get("rohan@bmsit.in")
    if rohan_id:
        cur.execute("""
            INSERT INTO projects (owner_id, title, description, course_context, team_size_min, team_size_max, schedule_notes, status)
            VALUES (?, 'Smart Campus Sensor Network & Navigation',
                    'Deploying IoT sensors across BMSIT&M campus for real-time room occupancy and ambient monitoring with web dashboard.',
                    'Innovation & Design Thinking (IDT)', 2, 3,
                    'Weekend work preferred.', 'published')
        """, (rohan_id,))
        p2_id = cur.lastrowid

        reqs2 = [
            ("IoT & Hardware", "must-have", 3.0),
            ("React", "must-have", 3.0),
            ("REST API Design", "preferred", 2.0)
        ]
        for sk_name, prio, wt in reqs2:
            if sk_name in skill_map:
                cur.execute("""
                    INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight)
                    VALUES (?, ?, ?, ?)
                """, (p2_id, skill_map[sk_name], prio, wt))

        cur.execute("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, 'Saturday', 'Morning (9AM-12PM)')", (p2_id,))
        if "IoT & Hardware" in interest_map:
            cur.execute("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (p2_id, interest_map["IoT & Hardware"]))

    # Project 3: Draft Project (to verify draft filtering)
    harsh_id = user_id_map.get("harsh@bmsit.in")
    if harsh_id:
        cur.execute("""
            INSERT INTO projects (owner_id, title, description, course_context, team_size_min, team_size_max, status)
            VALUES (?, 'Class Attendance with Facial Recognition (Draft)',
                    'Edge AI model to automate lab attendance with edge cameras.',
                    'Computer Vision Lab', 2, 4, 'draft')
        """, (harsh_id,))
        p3_id = cur.lastrowid
        if "Machine Learning" in skill_map:
            cur.execute("INSERT INTO project_skill_requirements (project_id, skill_id, priority, weight) VALUES (?, ?, 'must-have', 3.0)", (p3_id, skill_map["Machine Learning"]))

    conn.commit()
    conn.close()
    print("Database successfully initialized and seeded with BMSIT&M CSE 13 cohort data.")
