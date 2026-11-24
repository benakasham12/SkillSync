"""
Database configuration, dual-database architecture and helper functions for SkillSync.

Separates data into two dedicated local SQLite databases:
1. listings.db (Listings Database):
   Stores all publicly accessible project listings, skill criteria, availability requirements,
   team members, and applications so everyone can view and discover them.
2. users.db (Users Database):
   Stores user accounts, student profiles, authentication credentials, availability slots,
   messaging conversations, audit logs, and reports.

Maintains seamless backwards compatibility with existing Flask routes and tests
using SQLite's ATTACH DATABASE, TEMP VIEWs, and transparent write-routing.
"""

import sqlite3
import os
import re
import json
import atexit
from datetime import datetime
from flask import current_app, has_app_context, g
from werkzeug.security import generate_password_hash, check_password_hash

import tempfile
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if os.environ.get('VERCEL'):
    _tmp_dir = '/tmp' if os.path.isdir('/tmp') else tempfile.gettempdir()
    LISTINGS_DB_PATH = os.path.join(_tmp_dir, 'skillsync_listings.db')
    USERS_DB_PATH = os.path.join(_tmp_dir, 'skillsync_users.db')
else:
    LISTINGS_DB_PATH = os.path.join(ROOT_DIR, 'listings.db')
    USERS_DB_PATH = os.path.join(ROOT_DIR, 'users.db')

# Legacy alias for backwards compatibility
DB_PATH = LISTINGS_DB_PATH

USER_TABLES = {
    'users', 'student_profiles', 'student_skills', 'student_interests',
    'availability_slots', 'conversations', 'conversation_participants',
    'messages', 'message_attachments', 'message_read_status', 'reports', 'audit_events'
}

LISTINGS_TABLES = {
    'skills', 'interests', 'projects', 'project_skill_requirements',
    'project_availability_slots', 'project_interests', 'team_members',
    'project_applications', 'invitations'
}

_temp_dbs_to_clean = set()


def _cleanup_temp_dbs():
    for p in list(_temp_dbs_to_clean):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


atexit.register(_cleanup_temp_dbs)


def ensure_db_files_exist(listings_path=None, users_path=None):
    """
    On Vercel or ephemeral serverless environments, if local database files
    do not exist in /tmp, copy pre-populated bundled SQLite databases if available.
    """
    import shutil
    l_path = listings_path or LISTINGS_DB_PATH
    u_path = users_path or USERS_DB_PATH
    if os.environ.get('VERCEL'):
        bundled_l = os.path.join(ROOT_DIR, 'listings.db')
        bundled_u = os.path.join(ROOT_DIR, 'users.db')
        if (not os.path.exists(l_path) or os.path.getsize(l_path) == 0) and os.path.exists(bundled_l) and os.path.getsize(bundled_l) > 0:
            try:
                shutil.copy2(bundled_l, l_path)
            except Exception:
                pass
        if (not os.path.exists(u_path) or os.path.getsize(u_path) == 0) and os.path.exists(bundled_u) and os.path.getsize(bundled_u) > 0:
            try:
                shutil.copy2(bundled_u, u_path)
            except Exception:
                pass


def restore_project_from_session(project_id, db_path=None):
    """
    If a project is missing in ephemeral serverless instances (e.g. Vercel /tmp),
    restore it from the user's session cache if available.
    """
    from flask import has_request_context
    if not has_app_context() or not has_request_context():
        return None
    from flask import session
    cached = session.get('recent_projects') or {}
    p_data = cached.get(str(project_id))
    if not p_data:
        return None

    try:
        conn = get_db(db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO projects (
                id, owner_id, title, description, category, objectives, technologies,
                duration, collaboration_mode, availability, additional_requirements,
                course_context, team_size_min, team_size_max, schedule_notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p_data.get('id'), p_data.get('owner_id'), p_data.get('title'),
            p_data.get('description', ''), p_data.get('category', 'Other'),
            p_data.get('objectives', ''), p_data.get('technologies', ''),
            p_data.get('duration', '2–3 Months'), p_data.get('collaboration_mode', 'Hybrid'),
            p_data.get('availability', 'Flexible'), p_data.get('additional_requirements', ''),
            p_data.get('course_context', 'Innovation & Design Thinking (IDT)'),
            p_data.get('team_size_min', 2), p_data.get('team_size_max', 4),
            p_data.get('schedule_notes', ''), p_data.get('status', 'published')
        ))
        cur.execute("""
            INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'owner', CURRENT_TIMESTAMP)
        """, (p_data.get('id'), p_data.get('owner_id')))
        conn.commit()
        return query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True, db_path=db_path)
    except Exception:
        return None


def get_project_or_restore(project_id, db_path=None):
    """Fetch project from database, or restore from session cache if running on ephemeral serverless."""
    if not project_id:
        return None
    try:
        pid = int(project_id)
    except (ValueError, TypeError):
        pid = project_id

    project = query_db("SELECT * FROM projects WHERE id = ?", (pid,), one=True, db_path=db_path)
    if not project:
        project = restore_project_from_session(pid, db_path=db_path)
    return project


def resolve_db_paths(db_path=None):
    """
    Resolve listings and users database file paths from an optional db_path or app config.
    """
    if not db_path and has_app_context() and current_app and 'DATABASE' in current_app.config:
        db_path = current_app.config['DATABASE']

    if not db_path:
        return LISTINGS_DB_PATH, USERS_DB_PATH

    norm_path = os.path.abspath(db_path)
    if norm_path.endswith('skillsync.db'):
        listings_p = norm_path.replace('skillsync.db', 'listings.db')
        users_p = norm_path.replace('skillsync.db', 'users.db')
        return listings_p, users_p
    elif norm_path.endswith('listings.db'):
        listings_p = norm_path
        users_p = norm_path[:-11] + 'users.db'
        return listings_p, users_p
    elif norm_path.endswith('users.db'):
        users_p = norm_path
        listings_p = norm_path[:-8] + 'listings.db'
        return listings_p, users_p
    elif norm_path.endswith('.db'):
        listings_p = norm_path
        users_p = norm_path[:-3] + '_users.db'
        _temp_dbs_to_clean.add(users_p)
        return listings_p, users_p

    return norm_path, norm_path + '_users.db'


def rewrite_user_query(query):
    """
    Rewrites INSERT, UPDATE, and DELETE queries targeting USER_TABLES
    so they operate directly on the attached users_db database.
    """
    for tbl in USER_TABLES:
        pattern = rf"\b(INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM)\s+{tbl}\b"
        if re.search(pattern, query, flags=re.IGNORECASE):
            query = re.sub(pattern, rf"\1 users_db.{tbl}", query, flags=re.IGNORECASE)
    return query


class DualCursor(sqlite3.Cursor):
    def execute(self, sql, parameters=()):
        return super().execute(rewrite_user_query(sql), parameters)

    def executemany(self, sql, seq_of_parameters):
        return super().executemany(rewrite_user_query(sql), seq_of_parameters)


class DualConnection(sqlite3.Connection):
    def cursor(self, factory=DualCursor):
        return super().cursor(factory)

    def execute(self, sql, parameters=()):
        return super().execute(rewrite_user_query(sql), parameters)

    def executemany(self, sql, seq_of_parameters):
        return super().executemany(rewrite_user_query(sql), seq_of_parameters)


def init_users_db(users_path=None):
    """Initialize schema for the Users Database."""
    path = users_path or USERS_DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Student Profiles table
    CREATE TABLE IF NOT EXISTS student_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        display_name TEXT NOT NULL,
        usn TEXT,
        branch TEXT DEFAULT 'CSE',
        year TEXT DEFAULT '1st Year',
        section TEXT DEFAULT 'CSE-13',
        institution TEXT DEFAULT 'BMS Institute of Technology and Management',
        bio TEXT,
        github_url TEXT,
        linkedin_url TEXT,
        portfolio_url TEXT,
        visibility TEXT DEFAULT 'cohort_only',
        show_contact_after_accept INTEGER DEFAULT 1,
        is_match_ready INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Student Skills
    CREATE TABLE IF NOT EXISTS student_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        skill_id INTEGER NOT NULL,
        proficiency TEXT NOT NULL DEFAULT 'intermediate',
        self_reported INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, skill_id)
    );

    -- Student Interests
    CREATE TABLE IF NOT EXISTS student_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        interest_id INTEGER NOT NULL,
        UNIQUE(user_id, interest_id)
    );

    -- Student Weekly Availability Slots
    CREATE TABLE IF NOT EXISTS availability_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day_of_week TEXT NOT NULL,
        time_block TEXT NOT NULL,
        UNIQUE(user_id, day_of_week, time_block)
    );

    -- Conversations (Direct & Project Group Chats)
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_type TEXT NOT NULL,
        project_id INTEGER,
        conversation_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Conversation Participants
    CREATE TABLE IF NOT EXISTS conversation_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_read_at TIMESTAMP,
        last_read_message_id INTEGER DEFAULT 0,
        membership_status TEXT DEFAULT 'active',
        UNIQUE(conversation_id, student_id)
    );

    -- Messages
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        message_content TEXT NOT NULL,
        message_type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Message Attachments
    CREATE TABLE IF NOT EXISTS message_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        file_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT,
        file_size INTEGER,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Message Read Status
    CREATE TABLE IF NOT EXISTS message_read_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(message_id, student_id)
    );

    -- Reports / Moderation
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        target_type TEXT NOT NULL,
        target_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        admin_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );

    -- Audit Events / Analytics
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        target_type TEXT,
        target_id INTEGER,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indices
    CREATE INDEX IF NOT EXISTS idx_student_skills_user ON student_skills(user_id);
    CREATE INDEX IF NOT EXISTS idx_student_skills_skill ON student_skills(skill_id);
    CREATE INDEX IF NOT EXISTS idx_conv_part_student ON conversation_participants(student_id, membership_status);
    CREATE INDEX IF NOT EXISTS idx_conv_part_conv ON conversation_participants(conversation_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
    CREATE INDEX IF NOT EXISTS idx_attachments_msg ON message_attachments(message_id);
    CREATE INDEX IF NOT EXISTS idx_read_status_student ON message_read_status(student_id);
    CREATE INDEX IF NOT EXISTS idx_audit_events_name ON audit_events(event_name);
    """)

    # Safe column migrations
    user_cols_to_add = [
        ('conversation_participants', 'last_read_message_id', 'INTEGER DEFAULT 0')
    ]
    for tbl, col, col_type in user_cols_to_add:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def init_listings_db(listings_path=None):
    """Initialize schema for the Listings Database."""
    path = listings_path or LISTINGS_DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- Master Skills Catalog
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        active INTEGER DEFAULT 1
    );

    -- Master Interests Catalog
    CREATE TABLE IF NOT EXISTS interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT
    );

    -- Projects Table
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT DEFAULT 'Other',
        objectives TEXT,
        technologies TEXT,
        duration TEXT DEFAULT '2–3 Months',
        collaboration_mode TEXT DEFAULT 'Hybrid',
        availability TEXT DEFAULT 'Flexible',
        additional_requirements TEXT,
        course_context TEXT DEFAULT 'Innovation & Design Thinking (IDT)',
        team_size_min INTEGER DEFAULT 2,
        team_size_max INTEGER DEFAULT 4,
        schedule_notes TEXT,
        status TEXT DEFAULT 'draft',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Project Skill Requirements
    CREATE TABLE IF NOT EXISTS project_skill_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        priority TEXT DEFAULT 'must-have',
        proficiency_level TEXT DEFAULT 'intermediate',
        weight REAL DEFAULT 3.0,
        required_count INTEGER DEFAULT 1,
        UNIQUE(project_id, skill_id)
    );

    -- Project Interests
    CREATE TABLE IF NOT EXISTS project_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        interest_id INTEGER NOT NULL REFERENCES interests(id) ON DELETE CASCADE,
        UNIQUE(project_id, interest_id)
    );

    -- Project Availability Slots
    CREATE TABLE IF NOT EXISTS project_availability_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        day_of_week TEXT NOT NULL,
        time_block TEXT NOT NULL,
        UNIQUE(project_id, day_of_week, time_block)
    );

    -- Invitations
    CREATE TABLE IF NOT EXISTS invitations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        responded_at TIMESTAMP
    );

    -- Team Members
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL,
        role TEXT DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, user_id)
    );

    -- Project Applications
    CREATE TABLE IF NOT EXISTS project_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        applicant_id INTEGER NOT NULL,
        introduction TEXT,
        application_status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, applicant_id)
    );

    -- Indices
    CREATE INDEX IF NOT EXISTS idx_project_skills_project ON project_skill_requirements(project_id);
    CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON invitations(invitee_id, status);
    CREATE INDEX IF NOT EXISTS idx_team_members_project ON team_members(project_id);
    CREATE INDEX IF NOT EXISTS idx_project_applications_proj ON project_applications(project_id);
    CREATE INDEX IF NOT EXISTS idx_project_applications_applicant ON project_applications(applicant_id);
    """)

    # Safe column migrations
    listing_cols_to_add = [
        ('projects', 'category', "TEXT DEFAULT 'Other'"),
        ('projects', 'objectives', "TEXT"),
        ('projects', 'technologies', "TEXT"),
        ('projects', 'duration', "TEXT DEFAULT '2–3 Months'"),
        ('projects', 'collaboration_mode', "TEXT DEFAULT 'Hybrid'"),
        ('projects', 'availability', "TEXT DEFAULT 'Flexible'"),
        ('projects', 'additional_requirements', "TEXT"),
        ('project_skill_requirements', 'proficiency_level', "TEXT DEFAULT 'intermediate'")
    ]
    for tbl, col, col_type in listing_cols_to_add:
        try:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type};")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def _migrate_legacy_data_if_needed(listings_path, users_path):
    """
    Safely performs a one-time initial bootstrap migration from legacy skillsync.db
    into listings.db and users.db.
    If listings.db already contains projects, the migration is considered complete
    and will NEVER re-import old projects so that deleted projects never reappear.
    Once migrated, skillsync.db is safely archived to skillsync.db.migrated.
    """
    if os.path.abspath(listings_path) != os.path.abspath(LISTINGS_DB_PATH):
        return

    legacy_path = os.path.join(ROOT_DIR, 'skillsync.db')
    if not os.path.exists(legacy_path):
        return

    try:
        conn_l_check = sqlite3.connect(listings_path)
        existing_p_cnt = conn_l_check.execute("SELECT count(*) FROM projects").fetchone()[0]
        conn_l_check.close()

        # If listings already exist, legacy migration has completed.
        # Archive legacy database and never re-import deleted projects!
        if existing_p_cnt > 0:
            try:
                migrated_path = os.path.join(ROOT_DIR, 'skillsync.db.migrated')
                if not os.path.exists(migrated_path):
                    os.rename(legacy_path, migrated_path)
            except Exception:
                pass
            return

        old_conn = sqlite3.connect(legacy_path)
        old_conn.row_factory = sqlite3.Row

        conn_u = sqlite3.connect(users_path)
        conn_l = sqlite3.connect(listings_path)

        for tbl in USER_TABLES:
            try:
                rows = old_conn.execute(f"SELECT * FROM {tbl}").fetchall()
                if rows:
                    cols = rows[0].keys()
                    placeholders = ', '.join(['?'] * len(cols))
                    col_names = ', '.join(cols)
                    conn_u.executemany(f"INSERT OR IGNORE INTO {tbl} ({col_names}) VALUES ({placeholders})", [tuple(r) for r in rows])
            except Exception:
                pass

        for tbl in LISTINGS_TABLES:
            try:
                rows = old_conn.execute(f"SELECT * FROM {tbl}").fetchall()
                if rows:
                    cols = rows[0].keys()
                    placeholders = ', '.join(['?'] * len(cols))
                    col_names = ', '.join(cols)
                    conn_l.executemany(f"INSERT OR IGNORE INTO {tbl} ({col_names}) VALUES ({placeholders})", [tuple(r) for r in rows])
            except Exception:
                pass

        conn_u.commit()
        conn_l.commit()
        conn_u.close()
        conn_l.close()
        old_conn.close()

        try:
            migrated_path = os.path.join(ROOT_DIR, 'skillsync.db.migrated')
            if not os.path.exists(migrated_path):
                os.rename(legacy_path, migrated_path)
        except Exception:
            pass
    except Exception:
        pass


def init_db(db_path=None):
    """Initialize both Listings and Users databases and apply migrations."""
    listings_path, users_path = resolve_db_paths(db_path)
    init_listings_db(listings_path)
    init_users_db(users_path)
    _migrate_legacy_data_if_needed(listings_path, users_path)


def get_listings_db(db_path=None):
    """Direct connection to the Listings Database."""
    listings_path, _ = resolve_db_paths(db_path)
    conn = sqlite3.connect(listings_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_users_db(db_path=None):
    """Direct connection to the Users Database."""
    _, users_path = resolve_db_paths(db_path)
    conn = sqlite3.connect(users_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db(db_path=None):
    """
    Unified application database connection.
    Connects to listings.db as main and attaches users.db as users_db.
    Provides TEMP VIEWs for transparent reading of user tables, and uses DualConnection
    to seamlessly rewrite writes so queries targeting user tables write directly to users.db.
    Uses Flask's application context `g` for connection pooling across the request lifecycle.
    """
    if has_app_context() and hasattr(g, 'db') and g.db is not None:
        try:
            g.db.total_changes
            return g.db
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            g.db = None

    listings_path, users_path = resolve_db_paths(db_path)
    ensure_db_files_exist(listings_path, users_path)

    # Ensure files and tables exist
    if not os.path.exists(listings_path) or not os.path.exists(users_path):
        init_db(listings_path)

    conn = sqlite3.connect(listings_path, factory=DualConnection, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    users_abs = os.path.abspath(users_path).replace('\\', '/')
    conn.execute(f"ATTACH DATABASE '{users_abs}' AS users_db;")

    for tbl in USER_TABLES:
        conn.execute(f"CREATE TEMP VIEW IF NOT EXISTS {tbl} AS SELECT * FROM users_db.{tbl};")

    if has_app_context():
        g.db = conn

    return conn


def close_db(e=None):
    """Closes the current request's database connection if one exists."""
    if has_app_context() and hasattr(g, 'db'):
        db = g.db
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
            g.db = None


def query_db(query, args=(), one=False, db_path=None):
    """Execute a query and return rows as dictionaries."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
    if not has_app_context():
        conn.close()
    if rows:
        results = [dict(row) for row in rows]
        return results[0] if one else results
    return None if one else []


def execute_db(query, args=(), commit=True, db_path=None):
    """Execute insert/update/delete statement and return lastrowid or affected rows."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(query, args)
    if commit:
        conn.commit()
    last_id = cur.lastrowid
    rowcount = cur.rowcount
    if not has_app_context():
        conn.close()
    return last_id if last_id else rowcount
