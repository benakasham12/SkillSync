"""
Invitations routes implementing PRD FR-10, FR-11:
- Send invitation with duplicate check
- Accept / decline invitation with explicit status transition
- Automatic roster membership upon acceptance
- Enforces team size limits
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db
from app.routes.auth import login_required
from app.routes.projects import is_project_owner
from app.matching import compute_team_skill_coverage
from app.analytics import log_event

invitations_bp = Blueprint('invitations', __name__)


@invitations_bp.route('/invitations')
@login_required
def list_invitations():
    """Display student's incoming invitations and sent project invitations."""
    user_id = session['user_id']

    # Incoming invitations for this student
    incoming = query_db("""
        SELECT inv.*, p.title as project_title, p.course_context, p.description as project_description,
               sp.display_name as inviter_name, u.email as inviter_email
        FROM invitations inv
        JOIN projects p ON inv.project_id = p.id
        JOIN users u ON inv.inviter_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE inv.invitee_id = ?
        ORDER BY (inv.status = 'pending') DESC, inv.created_at DESC
    """, (user_id,))

    # Outgoing invitations sent by this student (for their projects)
    outgoing = query_db("""
        SELECT inv.*, p.title as project_title, sp.display_name as invitee_name, u.email as invitee_email
        FROM invitations inv
        JOIN projects p ON inv.project_id = p.id
        JOIN users u ON inv.invitee_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE inv.inviter_id = ?
        ORDER BY inv.created_at DESC
    """, (user_id,))

    return render_template('invitations.html', incoming=incoming, outgoing=outgoing)


@invitations_bp.route('/projects/<int:project_id>/invite', methods=['POST'])
@login_required
def send_invitation(project_id):
    """Send an invitation to a candidate (FR-10)."""
    user_id = session['user_id']
    from app.models import get_project_or_restore
    project = get_project_or_restore(project_id)

    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if not is_project_owner(project, user_id):
        flash('Unauthorized: Only the project owner can send invitations.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    invitee_id = request.form.get('invitee_id')
    message = request.form.get('message', '').strip()

    if not invitee_id:
        flash('No candidate specified.', 'danger')
        return redirect(url_for('projects.match_candidates', project_id=project_id))

    invitee_id = int(invitee_id)

    # 1. Prevent self-invite
    if invitee_id == user_id:
        flash('You cannot invite yourself to your own project.', 'danger')
        return redirect(url_for('projects.match_candidates', project_id=project_id))

    # 2. Check project status
    if project['status'] != 'published':
        flash('Cannot invite students to a project that is not published.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    # 3. Check capacity
    cov = compute_team_skill_coverage(project_id)
    if cov and cov['is_team_full']:
        flash(f"Team has already reached its maximum capacity of {cov['team_size_max']} members.", 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    # 4. Check if already a member
    already_member = query_db("SELECT 1 FROM team_members WHERE project_id = ? AND user_id = ?", (project_id, invitee_id), one=True)
    if already_member:
        flash('This student is already a member of your team.', 'warning')
        return redirect(url_for('projects.match_candidates', project_id=project_id))

    # 5. Check duplicate active invitation (FR-10)
    existing_invite = query_db("""
        SELECT id FROM invitations 
        WHERE project_id = ? AND invitee_id = ? AND status = 'pending'
    """, (project_id, invitee_id), one=True)
    if existing_invite:
        flash('An active pending invitation has already been sent to this student.', 'warning')
        return redirect(url_for('projects.match_candidates', project_id=project_id))

    inv_id = execute_db("""
        INSERT INTO invitations (project_id, inviter_id, invitee_id, status, message)
        VALUES (?, ?, ?, 'pending', ?)
    """, (project_id, user_id, invitee_id, message))

    log_event('invitation_sent', actor_id=user_id, target_type='invitation', target_id=inv_id,
              metadata={'project_id': project_id, 'invitee_id': invitee_id})

    flash('Invitation sent successfully!', 'success')
    return redirect(url_for('projects.match_candidates', project_id=project_id))


@invitations_bp.route('/invitations/<int:invitation_id>/respond', methods=['POST'])
@login_required
def respond_invitation(invitation_id):
    """Accept or decline an invitation (FR-10, FR-11)."""
    user_id = session['user_id']
    action = request.form.get('action') # 'accept' or 'decline'

    invitation = query_db("SELECT * FROM invitations WHERE id = ?", (invitation_id,), one=True)
    if not invitation or invitation['invitee_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('invitations.list_invitations'))

    if invitation['status'] != 'pending':
        flash(f"This invitation was already marked as {invitation['status']}.", 'info')
        return redirect(url_for('invitations.list_invitations'))

    if action == 'accept':
        project_id = invitation['project_id']
        project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)

        # Check capacity
        cov = compute_team_skill_coverage(project_id)
        if cov and cov['is_team_full']:
            flash('This project team is already full.', 'danger')
            return redirect(url_for('invitations.list_invitations'))

        # Add to team_members
        execute_db("""
            INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'member', CURRENT_TIMESTAMP)
        """, (project_id, user_id))

        # Add to project group chat
        from app.routes.messages import add_student_to_project_group
        add_student_to_project_group(project_id, user_id)

        # Update invitation status
        execute_db("""
            UPDATE invitations
            SET status = 'accepted', responded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (invitation_id,))

        log_event('invitation_accepted', actor_id=user_id, target_type='invitation', target_id=invitation_id,
                  metadata={'project_id': project_id})

        # Check if target team size reached
        cov_after = compute_team_skill_coverage(project_id)
        if cov_after and cov_after['current_team_size'] >= cov_after['team_size_min']:
            log_event('team_target_reached', actor_id=user_id, target_type='project', target_id=project_id,
                      metadata={'team_size': cov_after['current_team_size'], 'all_must_haves_covered': cov_after['all_must_haves_covered']})

        flash(f"You have joined '{project['title']}'! Your skills now contribute to the team's coverage.", 'success')

    elif action == 'decline':
        execute_db("""
            UPDATE invitations
            SET status = 'declined', responded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (invitation_id,))

        log_event('invitation_declined', actor_id=user_id, target_type='invitation', target_id=invitation_id,
                  metadata={'project_id': invitation['project_id']})

        flash('Invitation declined.', 'info')

    return redirect(url_for('invitations.list_invitations'))
