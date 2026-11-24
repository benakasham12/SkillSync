"""
Admin and Coordinator routes implementing PRD FR-13 and Section 9:
- Moderation reports review and resolution
- Real-time PRD Product Analytics and North Star Metric dashboard
- Complete User Management (view, edit profile, safe cascading delete, self-deletion guard)
- Complete Project Management (view, edit, delete any platform project)
"""

import os
import sqlite3
from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db, ROOT_DIR
from app.routes.auth import login_required, admin_required
from app.analytics import get_analytics_summary, log_event

admin_bp = Blueprint('admin', __name__)


def delete_user_account(target_user_id, admin_id=None):
    """
    Safely delete a user account and cascade deletion across all associated records:
    1. Identify student profile ID
    2. Delete all projects owned by the user (with all their requirements, slots, interests, team members, applications, invitations)
    3. Remove user from all other projects' team_members, project_applications, and invitations
    4. Remove skills, interests, availability_slots, student_profile
    5. Remove messaging participants and read statuses
    6. Remove moderation reports submitted by or filed against user profile
    7. Nullify audit events actor_id
    8. Delete from users table
    9. Delete from cloud database / Supabase if enabled
    """
    # 1. Resolve student profile ID
    profile = query_db("SELECT id FROM student_profiles WHERE user_id = ?", (target_user_id,), one=True)
    prof_id = profile['id'] if profile else None

    # 2. Find all projects owned by the user
    if prof_id:
        owned_projects = query_db(
            "SELECT id FROM projects WHERE owner_id = ? OR owner_id = ?",
            (target_user_id, prof_id)
        )
    else:
        owned_projects = query_db(
            "SELECT id FROM projects WHERE owner_id = ?",
            (target_user_id,)
        )

    for p in owned_projects:
        pid = p['id']
        execute_db("DELETE FROM project_skill_requirements WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM project_availability_slots WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM project_interests WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM team_members WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM project_applications WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM invitations WHERE project_id = ?", (pid,))
        execute_db("DELETE FROM reports WHERE target_type = 'project' AND target_id = ?", (pid,))
        execute_db("DELETE FROM projects WHERE id = ?", (pid,))

        # Clean legacy backup files if present
        for leg_name in ['skillsync.db', 'skillsync.db.migrated']:
            leg_path = os.path.join(ROOT_DIR, leg_name)
            if os.path.exists(leg_path):
                try:
                    with sqlite3.connect(leg_path) as leg_conn:
                        leg_conn.execute("DELETE FROM project_skill_requirements WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM project_availability_slots WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM project_interests WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM team_members WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM project_applications WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM invitations WHERE project_id = ?", (pid,))
                        leg_conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
                        leg_conn.commit()
                except Exception:
                    pass

        try:
            from app.supabase_client import is_cloud_enabled, delete_cloud_project
            if is_cloud_enabled():
                delete_cloud_project(pid)
        except Exception:
            pass

    # 3. Clean up user memberships in other projects
    execute_db("DELETE FROM team_members WHERE user_id = ?", (target_user_id,))
    execute_db("DELETE FROM project_applications WHERE applicant_id = ?", (target_user_id,))
    execute_db("DELETE FROM invitations WHERE inviter_id = ? OR invitee_id = ?", (target_user_id, target_user_id))
    if prof_id:
        execute_db("DELETE FROM team_members WHERE user_id = ?", (prof_id,))
        execute_db("DELETE FROM project_applications WHERE applicant_id = ?", (prof_id,))
        execute_db("DELETE FROM invitations WHERE inviter_id = ? OR invitee_id = ?", (prof_id, prof_id))

    # 4. Clean up user profile records
    execute_db("DELETE FROM student_skills WHERE user_id = ?", (target_user_id,))
    execute_db("DELETE FROM student_interests WHERE user_id = ?", (target_user_id,))
    execute_db("DELETE FROM availability_slots WHERE user_id = ?", (target_user_id,))
    execute_db("DELETE FROM student_profiles WHERE user_id = ?", (target_user_id,))

    # 5. Clean up messaging and reports
    execute_db("DELETE FROM conversation_participants WHERE student_id = ?", (target_user_id,))
    execute_db("DELETE FROM message_read_status WHERE student_id = ?", (target_user_id,))
    execute_db("DELETE FROM reports WHERE reporter_id = ? OR (target_type = 'profile' AND target_id = ?)", (target_user_id, target_user_id))
    execute_db("UPDATE audit_events SET actor_id = NULL WHERE actor_id = ?", (target_user_id,))

    # 6. Delete user record
    execute_db("DELETE FROM users WHERE id = ?", (target_user_id,))

    # 7. Cloud sync cleanup if enabled
    try:
        from app.supabase_client import is_cloud_enabled, supabase_request
        if is_cloud_enabled():
            supabase_request(f'profiles?id=eq.{target_user_id}', method='DELETE')
    except Exception:
        pass

    log_event('user_deleted_by_admin', actor_id=admin_id, target_type='user', target_id=target_user_id)


@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    """PRD Section 9 Analytics & Full Platform Management view."""
    metrics = get_analytics_summary()

    # Overview Metrics required by Admin Management
    total_reg = query_db("SELECT COUNT(*) as cnt FROM users", one=True)
    metrics['total_registered_users'] = total_reg['cnt'] if total_reg else 0

    active_cnt = query_db("SELECT COUNT(*) as cnt FROM users WHERE status = 'active'", one=True)
    metrics['active_users'] = active_cnt['cnt'] if active_cnt else 0

    proj_cnt = query_db("SELECT COUNT(*) as cnt FROM projects", one=True)
    metrics['total_projects_count'] = proj_cnt['cnt'] if proj_cnt else 0

    # User Management: Fetch all registered users with profiles
    users_list = query_db("""
        SELECT u.id, u.email, u.role, u.status, u.created_at,
               sp.id as profile_id,
               COALESCE(sp.display_name, u.email) as display_name,
               sp.usn, sp.branch, sp.year, sp.section, sp.institution
        FROM users u
        LEFT JOIN student_profiles sp ON u.id = sp.user_id
        ORDER BY u.id DESC
    """)

    # Project Management: Fetch all platform projects with owner information
    projects_list = query_db("""
        SELECT p.id, p.title, p.category, p.status, p.created_at, p.owner_id,
               p.team_size_min, p.team_size_max,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   'User #' || p.owner_id
               ) as owner_name,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_email
        FROM projects p
        ORDER BY p.id DESC
    """)

    return render_template(
        'admin/dashboard.html',
        metrics=metrics,
        users=users_list,
        projects=projects_list,
        current_admin_id=session.get('user_id')
    )


@admin_bp.route('/admin/users/<int:target_user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(target_user_id):
    """Admin route to view and update any user's profile and account settings."""
    target_user = query_db("SELECT * FROM users WHERE id = ?", (target_user_id,), one=True)
    if not target_user:
        flash('User account not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    target_profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (target_user_id,), one=True)

    if request.method == 'POST':
        # Account settings
        new_role = request.form.get('role', target_user['role']).strip().lower()
        new_status = request.form.get('status', target_user['status']).strip().lower()

        if new_role not in ('student', 'coordinator', 'admin'):
            new_role = target_user['role']
        if new_status not in ('active', 'deactivated'):
            new_status = target_user['status']

        execute_db("UPDATE users SET role = ?, status = ? WHERE id = ?", (new_role, new_status, target_user_id))

        # Profile settings
        display_name = request.form.get('display_name', '').strip()
        usn = request.form.get('usn', '').strip().upper()
        branch = request.form.get('branch', 'CSE').strip()
        year = request.form.get('year', '1st Year').strip()
        section = request.form.get('section', 'CSE-13').strip()
        institution = request.form.get('institution', 'BMS Institute of Technology and Management').strip()
        bio = request.form.get('bio', '').strip()
        github_url = request.form.get('github_url', '').strip() or None
        linkedin_url = request.form.get('linkedin_url', '').strip() or None
        portfolio_url = request.form.get('portfolio_url', '').strip() or None
        visibility = request.form.get('visibility', 'cohort_only')

        if target_profile:
            execute_db("""
                UPDATE student_profiles
                SET display_name = ?, usn = ?, branch = ?, year = ?, section = ?,
                    institution = ?, bio = ?, github_url = ?, linkedin_url = ?,
                    portfolio_url = ?, visibility = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (display_name, usn, branch, year, section, institution, bio, github_url, linkedin_url, portfolio_url, visibility, target_user_id))
        else:
            execute_db("""
                INSERT INTO student_profiles (user_id, display_name, usn, branch, year, section, institution, bio, github_url, linkedin_url, portfolio_url, visibility)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (target_user_id, display_name, usn, branch, year, section, institution, bio, github_url, linkedin_url, portfolio_url, visibility))

        log_event('user_profile_updated_by_admin', actor_id=session['user_id'], target_type='user', target_id=target_user_id)
        flash(f"Profile for {display_name or target_user['email']} updated successfully.", 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template(
        'admin/user_edit.html',
        target_user=target_user,
        target_profile=target_profile
    )


@admin_bp.route('/admin/users/<int:target_user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(target_user_id):
    """Admin route to permanently delete a user and cascade deletion to all related records."""
    current_admin_id = session.get('user_id')

    # Safety Guard: An administrator cannot delete their own account
    if target_user_id == current_admin_id:
        flash('Security Error: Administrators cannot delete their own account.', 'danger')
        return redirect(url_for('admin.dashboard'))

    target_user = query_db("SELECT email FROM users WHERE id = ?", (target_user_id,), one=True)
    if not target_user:
        flash('User account not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    user_email = target_user['email']
    delete_user_account(target_user_id, admin_id=current_admin_id)

    flash(f"User account '{user_email}' and all associated profile, project, and team records were deleted permanently.", 'info')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/projects/<int:project_id>/delete', methods=['POST'])
@admin_bp.route('/admin/projects/<project_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_project_admin(project_id):
    """Admin route to permanently delete any project on the platform across local and cloud databases."""
    is_ajax = (
        request.is_json
        or request.path.startswith('/api/')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    project = query_db("SELECT id, title FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Project not found.'}), 404
        flash('Project not found.', 'danger')
        return redirect(url_for('admin.dashboard'))

    execute_db("DELETE FROM project_skill_requirements WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_availability_slots WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_interests WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM team_members WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_applications WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM invitations WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM reports WHERE target_type = 'project' AND target_id = ?", (project_id,))
    execute_db("DELETE FROM projects WHERE id = ?", (project_id,))

    # Clean legacy backup files if present
    for leg_name in ['skillsync.db', 'skillsync.db.migrated']:
        leg_path = os.path.join(ROOT_DIR, leg_name)
        if os.path.exists(leg_path):
            try:
                with sqlite3.connect(leg_path) as leg_conn:
                    leg_conn.execute("DELETE FROM project_skill_requirements WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM project_availability_slots WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM project_interests WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM team_members WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM project_applications WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM invitations WHERE project_id = ?", (project_id,))
                    leg_conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                    leg_conn.commit()
            except Exception:
                pass

    cloud_deleted = False
    try:
        from app.supabase_client import is_cloud_enabled, delete_cloud_project
        if is_cloud_enabled():
            ok, _ = delete_cloud_project(project_id)
            cloud_deleted = ok
    except Exception:
        pass

    log_event('project_deleted_by_admin', actor_id=session['user_id'], target_type='project', target_id=project_id)

    if is_ajax:
        return jsonify({
            'success': True,
            'message': f"Project '{project['title']}' and all associated requirements and applications were deleted successfully.",
            'project_id': project_id,
            'cloud_deleted': cloud_deleted
        }), 200

    flash(f"Project '{project['title']}' and all associated requirements and applications were deleted successfully.", 'info')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/reports')
@login_required
@admin_required
def list_reports():
    """Moderation queue (FR-13)."""
    status_filter = request.args.get('status', 'pending')
    reports = query_db("""
        SELECT r.*, u.email as reporter_email, sp.display_name as reporter_name
        FROM reports r
        JOIN users u ON r.reporter_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE r.status = ?
        ORDER BY r.created_at DESC
    """, (status_filter,))

    return render_template('admin/reports.html', reports=reports, current_filter=status_filter)


@admin_bp.route('/reports', methods=['POST'])
@login_required
def submit_report():
    """Submit a report for an inappropriate profile or project (FR-13)."""
    reporter_id = session['user_id']
    target_type = request.form.get('target_type')  # 'profile' or 'project'
    target_id = int(request.form.get('target_id', 0))
    reason = request.form.get('reason', '').strip()

    if not reason or not target_type or not target_id:
        flash('Report reason is required.', 'danger')
        return redirect(request.referrer or url_for('projects.list_projects'))

    rep_id = execute_db("""
        INSERT INTO reports (reporter_id, target_type, target_id, reason, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (reporter_id, target_type, target_id, reason))

    log_event('report_submitted', actor_id=reporter_id, target_type=target_type, target_id=target_id)
    flash('Thank you for your report. Our coordinators will review it.', 'info')
    return redirect(request.referrer or url_for('projects.list_projects'))


@admin_bp.route('/admin/reports/<int:report_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_report(report_id):
    """Admin resolves or dismisses a report."""
    admin_id = session['user_id']
    action = request.form.get('action')  # 'resolve' or 'dismiss'
    admin_notes = request.form.get('admin_notes', '').strip()
    take_action = request.form.get('take_action')  # 'deactivate_user', 'close_project', 'none'

    report = query_db("SELECT * FROM reports WHERE id = ?", (report_id,), one=True)
    if not report:
        flash('Report not found.', 'danger')
        return redirect(url_for('admin.list_reports'))

    new_status = 'resolved' if action == 'resolve' else 'dismissed'

    # Apply enforcement action if selected
    if take_action == 'deactivate_user' and report['target_type'] == 'profile':
        execute_db("UPDATE users SET status = 'deactivated' WHERE id = ?", (report['target_id'],))
        flash(f"User #{report['target_id']} has been deactivated.", 'warning')
    elif take_action == 'close_project' and report['target_type'] == 'project':
        execute_db("UPDATE projects SET status = 'closed' WHERE id = ?", (report['target_id'],))
        flash(f"Project #{report['target_id']} has been closed.", 'warning')

    execute_db("""
        UPDATE reports
        SET status = ?, admin_notes = ?, resolved_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_status, admin_notes, report_id))

    flash(f"Report #{report_id} has been marked as {new_status}.", 'success')
    return redirect(url_for('admin.list_reports'))
