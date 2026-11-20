"""
Profile management routes implementing PRD FR-02, FR-03, FR-04, FR-12.
Manages student details, self-reported skills, availability grid, interests and privacy.
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db
from app.routes.auth import login_required
from app.analytics import log_event

profile_bp = Blueprint('profile', __name__)

TIME_BLOCKS = [
    "Morning (9AM-12PM)",
    "Afternoon (1PM-4PM)",
    "Evening (5PM-8PM)",
    "Night (8PM-11PM)"
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def check_and_update_match_readiness(user_id):
    """
    Evaluates if profile meets all requirements to be considered in project matches:
    - Basic info present (display_name, branch, year)
    - At least one skill declared
    - At least one availability block declared
    """
    profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (user_id,), one=True)
    if not profile:
        return False

    skills_cnt = query_db("SELECT COUNT(*) as cnt FROM student_skills WHERE user_id = ?", (user_id,), one=True)['cnt']
    slots_cnt = query_db("SELECT COUNT(*) as cnt FROM availability_slots WHERE user_id = ?", (user_id,), one=True)['cnt']

    is_ready = bool(
        profile['display_name'] and
        profile['branch'] and
        profile['year'] and
        skills_cnt > 0 and
        slots_cnt > 0
    )

    prev_ready = bool(profile['is_match_ready'])
    execute_db("UPDATE student_profiles SET is_match_ready = ? WHERE user_id = ?", (1 if is_ready else 0, user_id))

    if is_ready and not prev_ready:
        log_event('profile_completed', actor_id=user_id, target_type='profile', target_id=user_id)

    return is_ready


@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_id = session['user_id']

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_basic':
            display_name = request.form.get('display_name', '').strip()
            usn = request.form.get('usn', '').strip().upper()
            branch = request.form.get('branch', '').strip()
            year = request.form.get('year', '').strip()
            section = request.form.get('section', '').strip()
            bio = request.form.get('bio', '').strip()
            github_url = request.form.get('github_url', '').strip() or None
            linkedin_url = request.form.get('linkedin_url', '').strip() or None
            portfolio_url = request.form.get('portfolio_url', '').strip() or None
            visibility = request.form.get('visibility', 'cohort_only')
            show_contact = 1 if request.form.get('show_contact_after_accept') else 0

            execute_db("""
                UPDATE student_profiles
                SET display_name = ?, usn = ?, branch = ?, year = ?, section = ?,
                    bio = ?, github_url = ?, linkedin_url = ?, portfolio_url = ?,
                    visibility = ?, show_contact_after_accept = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (display_name, usn, branch, year, section, bio, github_url, linkedin_url, portfolio_url, visibility, show_contact, user_id))

            session['user_name'] = display_name
            check_and_update_match_readiness(user_id)
            flash('Basic profile information updated.', 'success')

        elif action == 'add_skill':
            skill_id = request.form.get('skill_id')
            proficiency = request.form.get('proficiency', 'intermediate')

            if skill_id:
                execute_db("""
                    INSERT OR REPLACE INTO student_skills (user_id, skill_id, proficiency, self_reported, updated_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                """, (user_id, int(skill_id), proficiency))
                check_and_update_match_readiness(user_id)
                log_event('skills_updated', actor_id=user_id, target_type='skill', target_id=int(skill_id))
                flash('Skill added to your profile (labelled as self-reported).', 'success')

        elif action == 'remove_skill':
            skill_id = request.form.get('skill_id')
            if skill_id:
                execute_db("DELETE FROM student_skills WHERE user_id = ? AND skill_id = ?", (user_id, int(skill_id)))
                check_and_update_match_readiness(user_id)
                flash('Skill removed.', 'info')

        elif action == 'update_availability':
            # Remove existing slots and batch insert newly checked slots
            execute_db("DELETE FROM availability_slots WHERE user_id = ?", (user_id,))
            selected_slots = request.form.getlist('slots')
            for slot_str in selected_slots:
                if '|' in slot_str:
                    day, block = slot_str.split('|', 1)
                    execute_db("INSERT INTO availability_slots (user_id, day_of_week, time_block) VALUES (?, ?, ?)", (user_id, day, block))

            check_and_update_match_readiness(user_id)
            log_event('availability_updated', actor_id=user_id, target_type='availability', target_id=user_id)
            flash('Availability schedule updated.', 'success')

        elif action == 'update_interests':
            execute_db("DELETE FROM student_interests WHERE user_id = ?", (user_id,))
            selected_interests = request.form.getlist('interest_ids')
            for iid in selected_interests:
                execute_db("INSERT INTO student_interests (user_id, interest_id) VALUES (?, ?)", (user_id, int(iid)))
            flash('Interest tags updated.', 'success')

        elif action == 'toggle_status':
            curr_user = query_db("SELECT status FROM users WHERE id = ?", (user_id,), one=True)
            new_status = 'deactivated' if curr_user['status'] == 'active' else 'active'
            execute_db("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
            flash(f"Your profile status is now {new_status}.", 'warning' if new_status == 'deactivated' else 'success')

        return redirect(url_for('profile.edit_profile'))

    # Load complete profile data
    profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (user_id,), one=True)
    user = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)

    my_skills = query_db("""
        SELECT ss.*, s.name as skill_name, s.category as skill_category
        FROM student_skills ss
        JOIN skills s ON ss.skill_id = s.id
        WHERE ss.user_id = ?
        ORDER BY s.category, s.name
    """, (user_id,))

    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")

    my_interests = query_db("""
        SELECT si.*, i.name as interest_name
        FROM student_interests si
        JOIN interests i ON si.interest_id = i.id
        WHERE si.user_id = ?
    """, (user_id,))
    my_interest_ids = {mi['interest_id'] for mi in my_interests}

    all_interests = query_db("SELECT * FROM interests ORDER BY category, name")

    slots_raw = query_db("SELECT day_of_week, time_block FROM availability_slots WHERE user_id = ?", (user_id,))
    my_slots = {f"{s['day_of_week']}|{s['time_block']}" for s in slots_raw}

    is_match_ready = check_and_update_match_readiness(user_id)

    return render_template(
        'profile.html',
        user=user,
        profile=profile,
        my_skills=my_skills,
        all_skills=all_skills,
        my_interests=my_interests,
        my_interest_ids=my_interest_ids,
        all_interests=all_interests,
        my_slots=my_slots,
        days=DAYS,
        time_blocks=TIME_BLOCKS,
        is_match_ready=is_match_ready
    )


@profile_bp.route('/students/<int:target_user_id>')
@login_required
def view_student_profile(target_user_id):
    """View read-only profile of another student, respecting privacy settings."""
    viewer_id = session['user_id']
    target_user = query_db("SELECT * FROM users WHERE id = ?", (target_user_id,), one=True)
    if not target_user:
        flash('Student not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    target_profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (target_user_id,), one=True)

    # Privacy check (FR-12 & Section 13)
    # Check if viewer is in a team with target or has accepted invitation
    shared_team = query_db("""
        SELECT 1 FROM team_members tm1
        JOIN team_members tm2 ON tm1.project_id = tm2.project_id
        WHERE tm1.user_id = ? AND tm2.user_id = ?
        UNION
        SELECT 1 FROM projects p
        JOIN team_members tm ON p.id = tm.project_id
        WHERE (p.owner_id = ? AND tm.user_id = ?) OR (p.owner_id = ? AND tm.user_id = ?)
    """, (viewer_id, target_user_id, viewer_id, target_user_id, target_user_id, viewer_id), one=True)

    can_view_contact = bool(shared_team) or not target_profile['show_contact_after_accept']

    skills = query_db("""
        SELECT ss.*, s.name as skill_name, s.category as skill_category
        FROM student_skills ss
        JOIN skills s ON ss.skill_id = s.id
        WHERE ss.user_id = ?
    """, (target_user_id,))

    interests = query_db("""
        SELECT i.name as interest_name
        FROM student_interests si
        JOIN interests i ON si.interest_id = i.id
        WHERE si.user_id = ?
    """, (target_user_id,))

    slots = query_db("SELECT day_of_week, time_block FROM availability_slots WHERE user_id = ?", (target_user_id,))

    log_event('candidate_profile_viewed', actor_id=viewer_id, target_type='profile', target_id=target_user_id)

    return render_template(
        'student_detail.html',
        target_user=target_user,
        profile=target_profile,
        skills=skills,
        interests=interests,
        slots=slots,
        can_view_contact=can_view_contact
    )


@profile_bp.route('/students')
def list_students():
    """Renders the dedicated Explore Students directory with search and filter capabilities."""
    search_q = request.args.get('q', '').strip()
    branch_filter = request.args.get('branch', '').strip()
    skill_filter = request.args.get('skill', '').strip()

    sql = """
        SELECT sp.*, u.email
        FROM student_profiles sp
        JOIN users u ON sp.user_id = u.id
        WHERE 1=1
    """
    params = []

    if search_q:
        sql += " AND (sp.display_name LIKE ? OR sp.bio LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])

    if branch_filter:
        sql += " AND sp.branch = ?"
        params.append(branch_filter)

    if skill_filter:
        sql += """ AND sp.user_id IN (
            SELECT ss2.user_id FROM student_skills ss2
            JOIN skills s2 ON ss2.skill_id = s2.id
            WHERE s2.name LIKE ?
        )"""
        params.append(f"%{skill_filter}%")

    sql += " ORDER BY sp.is_match_ready DESC, sp.display_name ASC"

    students = query_db(sql, tuple(params))

    # Fetch top skills for each student
    for s in students:
        s_skills = query_db("""
            SELECT ss.proficiency, s.name, s.category
            FROM student_skills ss
            JOIN skills s ON ss.skill_id = s.id
            WHERE ss.user_id = ?
            ORDER BY ss.proficiency DESC
            LIMIT 5
        """, (s['user_id'],))
        s['skills'] = s_skills

    branches = query_db("SELECT DISTINCT branch FROM student_profiles WHERE branch IS NOT NULL AND branch != '' ORDER BY branch ASC")
    all_skills = query_db("SELECT id, name FROM skills ORDER BY name ASC")

    return render_template(
        'students.html',
        students=students,
        branches=branches,
        all_skills=all_skills,
        search_q=search_q,
        selected_branch=branch_filter,
        selected_skill=skill_filter
    )

