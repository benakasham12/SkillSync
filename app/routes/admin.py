"""
Admin and Coordinator routes implementing PRD FR-13 and Section 9:
- Moderation reports review and resolution
- Real-time PRD Product Analytics and North Star Metric dashboard
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db
from app.routes.auth import login_required, admin_required
from app.analytics import get_analytics_summary, log_event

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    """PRD Section 9 Analytics & Success Metrics view."""
    metrics = get_analytics_summary()
    return render_template('admin/dashboard.html', metrics=metrics)


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
    target_type = request.form.get('target_type') # 'profile' or 'project'
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
    action = request.form.get('action') # 'resolve' or 'dismiss'
    admin_notes = request.form.get('admin_notes', '').strip()
    take_action = request.form.get('take_action') # 'deactivate_user', 'close_project', 'none'

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
