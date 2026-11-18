"""
Database configuration, schema and helper functions for SkillSync.
Uses SQLite with sqlite3.Row for relational constraints, foreign keys and clean dict access.
"""

import sqlite3
import os
import json
from datetime import datetime
from flask import current_app, has_app_context
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = '/tmp/skillsync.db' if os.environ.get('VERCEL') else os.path.join(os.path.dirname(os.path.dirname(__file__)), 'skillsync.db')


def get_db(db_path=None):
    """Obtain a SQLite connection with foreign keys enabled and row factory set to sqlite3.Row."""
    if not db_path and has_app_context() and current_app and 'DATABASE' in current_app.config:
        db_path = current_app.config['DATABASE']
    if not db_path and os.environ.get('VERCEL'):
        db_path = '/tmp/skillsync.db'
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    """Initialize database tables according to PRD Section 7.1 specification."""
    conn = get_db(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student', -- 'student', 'admin', 'coordinator'
        status TEXT NOT NULL DEFAULT 'active', -- 'active', 'deactivated'
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
        visibility TEXT DEFAULT 'cohort_only', -- 'public', 'cohort_only', 'private'
        show_contact_after_accept INTEGER DEFAULT 1,
        is_match_ready INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Master Skills Catalog
    CREATE TABLE IF NOT EXISTS skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL, -- 'Frontend', 'Backend', 'Design', 'Data/AI', 'Tools', 'Soft Skills'
        active INTEGER DEFAULT 1
    );

    -- Student Skills
    CREATE TABLE IF NOT EXISTS student_skills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        proficiency TEXT NOT NULL DEFAULT 'intermediate', -- 'beginner', 'intermediate', 'advanced'
        self_reported INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, skill_id)
    );

    -- Master Interests Catalog
    CREATE TABLE IF NOT EXISTS interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        category TEXT
    );

    -- Student Interests
    CREATE TABLE IF NOT EXISTS student_interests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        interest_id INTEGER NOT NULL REFERENCES interests(id) ON DELETE CASCADE,
        UNIQUE(user_id, interest_id)
    );

    -- Student Weekly Availability Slots
    CREATE TABLE IF NOT EXISTS availability_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        day_of_week TEXT NOT NULL, -- 'Monday', 'Tuesday', etc.
        time_block TEXT NOT NULL,  -- 'Morning (9AM-12PM)', 'Afternoon (1PM-4PM)', 'Evening (5PM-8PM)', 'Night (8PM-11PM)'
        UNIQUE(user_id, day_of_week, time_block)
    );

    -- Projects Table
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        description TEXT,
        course_context TEXT DEFAULT 'Innovation & Design Thinking (IDT)',
        team_size_min INTEGER DEFAULT 2,
        team_size_max INTEGER DEFAULT 4,
        schedule_notes TEXT,
        status TEXT DEFAULT 'draft', -- 'draft', 'published', 'closed', 'archived'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Project Skill Requirements
    CREATE TABLE IF NOT EXISTS project_skill_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
        priority TEXT DEFAULT 'must-have', -- 'must-have', 'preferred'
        weight REAL DEFAULT 3.0,          -- must-have default: 3.0, preferred default: 1.0
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

    -- Project Desired Availability Slots
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
        inviter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        invitee_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        status TEXT DEFAULT 'pending', -- 'pending', 'accepted', 'declined', 'cancelled'
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        responded_at TIMESTAMP
    );

    -- Team Members
    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role TEXT DEFAULT 'member', -- 'owner', 'member'
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, user_id)
    );

    -- Reports / Moderation
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        target_type TEXT NOT NULL, -- 'profile', 'project'
        target_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'pending', -- 'pending', 'resolved', 'dismissed'
        admin_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );

    -- Audit Events / Product Analytics (PRD Section 9.1)
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        target_type TEXT,
        target_id INTEGER,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indices for performance
    CREATE INDEX IF NOT EXISTS idx_student_skills_user ON student_skills(user_id);
    CREATE INDEX IF NOT EXISTS idx_student_skills_skill ON student_skills(skill_id);
    CREATE INDEX IF NOT EXISTS idx_project_skills_project ON project_skill_requirements(project_id);
    CREATE INDEX IF NOT EXISTS idx_invitations_invitee ON invitations(invitee_id, status);
    CREATE INDEX IF NOT EXISTS idx_team_members_project ON team_members(project_id);
    CREATE INDEX IF NOT EXISTS idx_audit_events_name ON audit_events(event_name);
    """)

    conn.commit()
    conn.close()


def query_db(query, args=(), one=False, db_path=None):
    """Execute a query and return rows as dictionaries."""
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(query, args)
    rows = cur.fetchall()
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
    conn.close()
    return last_id if last_id else rowcount
