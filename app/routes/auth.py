"""
Authentication routes and session management.
Supports registration, login, logout, profile validation, and demo switching.
"""

from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import query_db, execute_db
from app.analytics import log_event

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.path))
        if session.get('user_role') not in ('admin', 'coordinator'):
            flash('Administrator privileges required.', 'danger')
            return redirect(url_for('projects.list_projects'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Retrieve currently logged in user record and profile."""
    uid = session.get('user_id')
    if not uid:
        return None
    user = query_db("SELECT id, email, role, status FROM users WHERE id = ?", (uid,), one=True)
    if not user:
        return None
    profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (uid,), one=True)
    return {'user': user, 'profile': profile}


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('projects.list_projects'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        usn = request.form.get('usn', '').strip().upper()
        branch = request.form.get('branch', 'CSE').strip()
        year = request.form.get('year', '1st Year').strip()
        section = request.form.get('section', 'CSE-13').strip()

        # Validation per PRD FR-01 & Section 13
        if not email or not password or not display_name:
            flash('Email, password, and full name are required.', 'danger')
            return render_template('register.html', email=email, display_name=display_name, usn=usn)

        # Check existing user
        existing = query_db("SELECT id FROM users WHERE email = ?", (email,), one=True)
        if existing:
            flash('An account with this email already exists.', 'danger')
            return render_template('register.html', email=email, display_name=display_name, usn=usn)

        hashed_pw = generate_password_hash(password)
        user_id = execute_db(
            "INSERT INTO users (email, password_hash, role, status) VALUES (?, ?, 'student', 'active')",
            (email, hashed_pw)
        )

        execute_db("""
            INSERT INTO student_profiles (user_id, display_name, usn, branch, year, section, institution, is_match_ready)
            VALUES (?, ?, ?, ?, ?, ?, 'BMS Institute of Technology and Management', 0)
        """, (user_id, display_name, usn, branch, year, section))

        log_event('account_created', actor_id=user_id, target_type='user', target_id=user_id)

        session['user_id'] = user_id
        session['user_email'] = email
        session['user_name'] = display_name
        session['user_role'] = 'student'

        flash('Account successfully created! Please complete your skills and availability to become match-ready.', 'success')
        return redirect(url_for('profile.edit_profile'))

    return render_template('register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('projects.list_projects'))

    next_url = request.args.get('next') or request.form.get('next') or url_for('projects.list_projects')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', email=email, next=next_url)

        if user['status'] == 'deactivated':
            flash('Your account has been deactivated. Please contact an administrator.', 'danger')
            return render_template('login.html', email=email, next=next_url)

        profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (user['id'],), one=True)

        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = profile['display_name'] if profile else user['email'].split('@')[0]
        session['user_role'] = user['role']

        flash(f"Welcome back, {session['user_name']}!", 'success')
        return redirect(next_url)

    # Provide demo student list for convenience
    demo_users = query_db("""
        SELECT u.email, u.role, sp.display_name, sp.section
        FROM users u
        LEFT JOIN student_profiles sp ON u.id = sp.user_id
        ORDER BY u.role DESC, sp.display_name ASC
    """)
    return render_template('login.html', demo_users=demo_users, next=next_url)


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/switch/<email>')
def switch_user(email):
    """Convenience helper for presentation & evaluation to switch demo personas quickly."""
    user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if user:
        profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (user['id'],), one=True)
        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = profile['display_name'] if profile else user['email'].split('@')[0]
        session['user_role'] = user['role']
        flash(f"Switched persona to: {session['user_name']} ({user['email']})", 'info')
    return redirect(request.referrer or url_for('projects.list_projects'))
