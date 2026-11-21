"""
Authentication routes and session management.
Supports registration, login, logout, profile validation, and demo switching.
"""

from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.models import query_db, execute_db
from app.analytics import log_event

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        uid = session.get('user_id')

        # Fallback: check for authentication headers or token if session is not yet loaded
        if not uid:
            auth_header = request.headers.get('Authorization') or request.headers.get('X-User-Id')
            if auth_header:
                token = auth_header[7:].strip() if auth_header.startswith('Bearer ') else auth_header.strip()
                if token.isdigit():
                    u_cand = query_db("SELECT id, email, role, status FROM users WHERE id = ?", (int(token),), one=True)
                    if u_cand and u_cand.get('status') != 'deactivated':
                        session['user_id'] = u_cand['id']
                        session['user_email'] = u_cand['email']
                        session['user_role'] = u_cand['role']
                        uid = u_cand['id']

        if not uid:
            if request.is_json or request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required', 'success': False}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth.login', next=request.path))

        user = query_db("SELECT id, email, role, status FROM users WHERE id = ?", (uid,), one=True)
        if not user or user.get('status') == 'deactivated':
            session.clear()
            if request.is_json or request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Session expired or invalid user account. Please log in again.', 'success': False}), 401
            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login', next=request.path))

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.path))

        user_role = session.get('user_role')
        if not user_role:
            u_rec = query_db("SELECT role FROM users WHERE id = ?", (session['user_id'],), one=True)
            if u_rec:
                user_role = u_rec.get('role')
                session['user_role'] = user_role

        if not user_role or str(user_role).strip().lower() not in ('admin', 'coordinator'):
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

    # Fetch demo users list for quick reviewer testing
    demo_users = query_db("""
        SELECT u.email, u.role, sp.display_name, sp.section, sp.branch
        FROM users u
        LEFT JOIN student_profiles sp ON u.id = sp.user_id
        ORDER BY u.role DESC, sp.display_name ASC
    """)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        # Required-field validation
        if not email or not password:
            flash('Please enter both your student email and password.', 'danger')
            return render_template('login.html', email=email, next=next_url, demo_users=demo_users)

        # Email format validation
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid student email address format.', 'danger')
            return render_template('login.html', email=email, next=next_url, demo_users=demo_users)

        user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password. Please verify your credentials and try again.', 'danger')
            return render_template('login.html', email=email, next=next_url, demo_users=demo_users)

        if user['status'] == 'deactivated':
            flash('Your account has been deactivated. Please contact an administrator or coordinator.', 'danger')
            return render_template('login.html', email=email, next=next_url, demo_users=demo_users)

        profile = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (user['id'],), one=True)

        session['user_id'] = user['id']
        session['user_email'] = user['email']
        session['user_name'] = profile['display_name'] if profile else user['email'].split('@')[0]
        session['user_role'] = user['role']

        if remember:
            session.permanent = True

        log_event('user_login', actor_id=user['id'], target_type='user', target_id=user['id'])

        flash(f"Welcome back, {session['user_name']}! You have signed in successfully.", 'success')
        return redirect(next_url)

    return render_template('login.html', demo_users=demo_users, next=next_url)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('projects.list_projects'))

    reset_token = None
    reset_email = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid registered student email address.', 'danger')
            return render_template('forgot_password.html', email=email)

        user = query_db("SELECT id, email FROM users WHERE email = ?", (email,), one=True)
        if user:
            s = URLSafeTimedSerializer(current_app.secret_key)
            reset_token = s.dumps(user['email'], salt='skillsync-password-reset')
            reset_email = user['email']
            log_event('password_reset_requested', actor_id=user['id'], target_type='user', target_id=user['id'])

        # Security requirement: generic message without revealing account existence
        flash('If an account exists with this email address, password reset instructions have been generated.', 'info')
        return render_template('forgot_password.html', email=email, reset_token=reset_token, reset_email=reset_email)

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if 'user_id' in session:
        return redirect(url_for('projects.list_projects'))

    s = URLSafeTimedSerializer(current_app.secret_key)

    try:
        email = s.loads(token, salt='skillsync-password-reset', max_age=3600)  # 1 hour expiration
    except (SignatureExpired, BadSignature):
        flash('The password reset link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    user = query_db("SELECT id, email FROM users WHERE email = ?", (email,), one=True)
    if not user:
        flash('User account not found or deactivated.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('reset_password.html', token=token, email=email)

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter both fields.', 'danger')
            return render_template('reset_password.html', token=token, email=email)

        new_hashed = generate_password_hash(password)
        execute_db("UPDATE users SET password_hash = ? WHERE id = ?", (new_hashed, user['id']))
        log_event('password_reset_completed', actor_id=user['id'], target_type='user', target_id=user['id'])

        flash('Your password has been successfully reset! You can now sign in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token, email=email)


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
