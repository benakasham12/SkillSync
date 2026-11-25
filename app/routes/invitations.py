"""
Invitations routes implementing PRD FR-10, FR-11:
- Send invitation with duplicate check
- Accept / decline invitation with explicit status transition
- Automatic roster membership upon acceptance
- Enforces team size limits
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.models import query_db, execute_db
from app.routes.auth import login_required
from app.routes.projects import is_project_owner
from app.matching import compute_team_skill_coverage
from app.analytics import log_event

invitations_bp = Blueprint('invitations', __name__)


def sign_record_token(payload, salt='skillsync-record-token'):
    """Create a tamper-proof signed token for serverless cross-container state recovery."""
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps(payload, salt=salt)
    except Exception:
        return ''


def verify_record_token(token, salt='skillsync-record-token', max_age=86400 * 14):
    """Verify and decode a signed state recovery token."""
    if not token:
        return None
    try:
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.loads(token, salt=salt, max_age=max_age)
    except (SignatureExpired, BadSignature, Exception):
        return None


def hydrate_invitations_from_session():
    """Hydrate any invitations cached in the browser session into local SQLite."""
    from app.models import get_project_or_restore
    cached_invs = session.get('invitations_cache') or []
    for inv in cached_invs:
        try:
            if inv.get('project_id'):
                get_project_or_restore(inv.get('project_id'))
            execute_db("""
                INSERT OR IGNORE INTO invitations (id, project_id, inviter_id, invitee_id, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                inv.get('id'),
                inv.get('project_id'),
                inv.get('inviter_id'),
                inv.get('invitee_id'),
                inv.get('status', 'pending'),
                inv.get('message', '')
            ))
        except Exception:
            pass


def is_same_user_or_profile(user_id, target_id, db_path=None):
    """
    Check if target_id matches user_id directly or through student_profiles.
    Supports both integer IDs, UUIDs, and profile IDs.
    """
    if user_id is None or target_id is None:
        return False
    u_str = str(user_id).strip()
    t_str = str(target_id).strip()
    if u_str == t_str:
        return True
    try:
        if int(u_str) == int(t_str):
            return True
    except (ValueError, TypeError):
        pass

    prof = query_db(
        "SELECT id, user_id FROM student_profiles WHERE (user_id = ? AND id = ?) OR (id = ? AND user_id = ?)",
        (u_str, t_str, u_str, t_str),
        one=True,
        db_path=db_path
    )
    return bool(prof)


@invitations_bp.route('/invitations')
@login_required
def list_invitations():
    """Display student's incoming/sent project invitations and incoming/outgoing join requests (applications)."""
    user_id = session['user_id']

    # Hydrate any invitations and applications cached in the browser session (serverless cross-container consistency)
    hydrate_invitations_from_session()
    cached_apps = session.get('pending_applications_cache') or []
    if cached_apps:
        from app.models import get_project_or_restore
        for a in cached_apps:
            try:
                if a.get('project_id'):
                    get_project_or_restore(a.get('project_id'))
                execute_db("""
                    INSERT OR IGNORE INTO project_applications (id, project_id, applicant_id, introduction, application_status)
                    VALUES (?, ?, ?, ?, ?)
                """, (a.get('id'), a.get('project_id'), a.get('applicant_id'), a.get('introduction', ''), a.get('application_status', 'pending')))
            except Exception:
                pass

    # 1. Incoming direct invitations to this student
    incoming = query_db("""
        SELECT inv.*, p.title as project_title, p.course_context, p.description as project_description,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = inv.inviter_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = inv.inviter_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = inv.inviter_id LIMIT 1),
                   'Project Creator'
               ) as inviter_name,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = inv.inviter_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = inv.inviter_id LIMIT 1),
                   ''
               ) as inviter_email
        FROM invitations inv
        JOIN projects p ON inv.project_id = p.id
        WHERE (inv.invitee_id = ? OR inv.invitee_id IN (SELECT id FROM student_profiles WHERE user_id = ?))
        ORDER BY (inv.status = 'pending') DESC, inv.created_at DESC
    """, (user_id, user_id))

    # 2. Outgoing direct invitations sent by this student (for their projects)
    outgoing = query_db("""
        SELECT inv.*, p.title as project_title,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = inv.invitee_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = inv.invitee_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = inv.invitee_id LIMIT 1),
                   'Candidate'
               ) as invitee_name,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = inv.invitee_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = inv.invitee_id LIMIT 1),
                   ''
               ) as invitee_email
        FROM invitations inv
        JOIN projects p ON inv.project_id = p.id
        WHERE (inv.inviter_id = ? OR inv.inviter_id IN (SELECT id FROM student_profiles WHERE user_id = ?))
        ORDER BY inv.created_at DESC
    """, (user_id, user_id))

    # 3. Incoming Join Requests (applications submitted by other students to projects owned by this user)
    incoming_applications = query_db("""
        SELECT pa.*, p.title as project_title, p.course_context,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = pa.applicant_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = pa.applicant_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = pa.applicant_id LIMIT 1),
                   'Student Applicant'
               ) as applicant_name,
               COALESCE(
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.user_id = pa.applicant_id LIMIT 1),
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.id = pa.applicant_id LIMIT 1),
                   'CSE'
               ) as applicant_branch,
               COALESCE(
                   (SELECT sp.year FROM student_profiles sp WHERE sp.user_id = pa.applicant_id LIMIT 1),
                   (SELECT sp.year FROM student_profiles sp WHERE sp.id = pa.applicant_id LIMIT 1),
                   '1st Year'
               ) as applicant_year,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = pa.applicant_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = pa.applicant_id LIMIT 1),
                   ''
               ) as applicant_email
        FROM project_applications pa
        JOIN projects p ON pa.project_id = p.id
        WHERE (p.owner_id = ? OR p.owner_id IN (SELECT id FROM student_profiles WHERE user_id = ?))
        ORDER BY (pa.application_status = 'pending') DESC, pa.created_at DESC
    """, (user_id, user_id))

    # 4. Outgoing Join Requests (applications sent by this student to other projects)
    outgoing_applications = query_db("""
        SELECT pa.*, p.title as project_title, p.course_context,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   'Project Creator'
               ) as owner_name,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_email
        FROM project_applications pa
        JOIN projects p ON pa.project_id = p.id
        WHERE (pa.applicant_id = ? OR pa.applicant_id IN (SELECT id FROM student_profiles WHERE user_id = ?))
        ORDER BY (pa.application_status = 'pending') DESC, pa.created_at DESC
    """, (user_id, user_id))

    # Attach signed recovery tokens to pending cards for serverless cross-container safety
    incoming_enriched = []
    for inv in incoming:
        inv_d = dict(inv)
        proj_snap = query_db("SELECT id, owner_id, title, team_size_min, team_size_max, status FROM projects WHERE id = ?", (inv_d['project_id'],), one=True)
        inv_d['inv_token'] = sign_record_token({
            'id': inv_d['id'],
            'project_id': inv_d['project_id'],
            'inviter_id': inv_d['inviter_id'],
            'invitee_id': inv_d['invitee_id'],
            'status': inv_d['status'],
            'message': inv_d.get('message', ''),
            'project': dict(proj_snap) if proj_snap else None
        }, salt='skillsync-inv-token')
        incoming_enriched.append(inv_d)

    incoming_apps_enriched = []
    for app_row in incoming_applications:
        app_d = dict(app_row)
        proj_snap = query_db("SELECT id, owner_id, title, team_size_min, team_size_max, status FROM projects WHERE id = ?", (app_d['project_id'],), one=True)
        app_d['app_token'] = sign_record_token({
            'id': app_d['id'],
            'project_id': app_d['project_id'],
            'applicant_id': app_d['applicant_id'],
            'introduction': app_d.get('introduction', ''),
            'application_status': app_d.get('application_status', 'pending'),
            'project': dict(proj_snap) if proj_snap else None
        }, salt='skillsync-app-token')
        incoming_apps_enriched.append(app_d)

    return render_template(
        'invitations.html',
        incoming=incoming_enriched,
        outgoing=outgoing,
        incoming_applications=incoming_apps_enriched,
        outgoing_applications=outgoing_applications
    )


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

    # Cache project in session for serverless multi-container consistency
    try:
        recent = session.get('recent_projects') or {}
        if str(project_id) not in recent:
            recent[str(project_id)] = dict(project)
            session['recent_projects'] = recent
            session.modified = True
    except Exception:
        pass

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

    # Cache invitation in session for serverless multi-container consistency
    try:
        cached_invs = session.get('invitations_cache') or []
        cached_invs.append({
            'id': inv_id,
            'project_id': project_id,
            'inviter_id': user_id,
            'invitee_id': invitee_id,
            'status': 'pending',
            'message': message
        })
        session['invitations_cache'] = cached_invs
        session.modified = True
    except Exception:
        pass

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

    hydrate_invitations_from_session()
    invitation = query_db("SELECT * FROM invitations WHERE id = ?", (invitation_id,), one=True)

    # Stateless signed token recovery if running on an isolated serverless container
    if not invitation:
        inv_token = request.form.get('inv_token')
        token_data = verify_record_token(inv_token, salt='skillsync-inv-token')
        if token_data and str(token_data.get('id')) == str(invitation_id):
            proj_snap = token_data.get('project')
            if proj_snap and proj_snap.get('id'):
                try:
                    execute_db("""
                        INSERT OR IGNORE INTO projects (id, owner_id, title, team_size_min, team_size_max, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        proj_snap.get('id'), proj_snap.get('owner_id'),
                        proj_snap.get('title', 'Project'), proj_snap.get('team_size_min', 2),
                        proj_snap.get('team_size_max', 4), proj_snap.get('status', 'published')
                    ))
                    execute_db("""
                        INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
                        VALUES (?, ?, 'owner', CURRENT_TIMESTAMP)
                    """, (proj_snap.get('id'), proj_snap.get('owner_id')))
                except Exception:
                    pass
            try:
                execute_db("""
                    INSERT OR IGNORE INTO invitations (id, project_id, inviter_id, invitee_id, status, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    token_data.get('id'), token_data.get('project_id'),
                    token_data.get('inviter_id'), token_data.get('invitee_id'),
                    token_data.get('status', 'pending'), token_data.get('message', '')
                ))
                invitation = query_db("SELECT * FROM invitations WHERE id = ?", (invitation_id,), one=True)
            except Exception:
                pass

    if not invitation:
        flash('Invitation not found.', 'danger')
        return redirect(request.referrer or url_for('invitations.list_invitations'))

    if not is_same_user_or_profile(user_id, invitation['invitee_id']):
        flash('Unauthorized action: This invitation was not addressed to your account.', 'danger')
        return redirect(request.referrer or url_for('invitations.list_invitations'))

    if invitation['status'] != 'pending':
        flash(f"This invitation was already marked as {invitation['status']}.", 'info')
        return redirect(request.referrer or url_for('invitations.list_invitations'))

    if action == 'accept':
        project_id = invitation['project_id']
        from app.models import get_project_or_restore
        project = get_project_or_restore(project_id)
        if not project:
            flash('Project not found.', 'danger')
            return redirect(request.referrer or url_for('invitations.list_invitations'))

        # Check capacity
        cov = compute_team_skill_coverage(project_id)
        if cov and cov['is_team_full']:
            flash('This project team is already full.', 'danger')
            return redirect(request.referrer or url_for('invitations.list_invitations'))

        # Add to team_members
        execute_db("""
            INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'member', CURRENT_TIMESTAMP)
        """, (project_id, user_id))

        # Synchronize into session caches for serverless multi-container consistency
        try:
            cached_tm = session.get('team_members_cache') or {}
            proj_m = cached_tm.get(str(project_id)) or []
            if user_id not in proj_m and not any(isinstance(x, dict) and x.get('user_id') == user_id for x in proj_m):
                proj_m.append(user_id)
            cached_tm[str(project_id)] = proj_m
            session['team_members_cache'] = cached_tm
            session.modified = True
        except Exception:
            pass

        # Add to project group chat
        try:
            from app.routes.messages import add_student_to_project_group
            add_student_to_project_group(project_id, user_id)
        except Exception:
            pass

        # Update invitation status
        execute_db("""
            UPDATE invitations
            SET status = 'accepted', responded_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (invitation_id,))

        try:
            cached_invs = session.get('invitations_cache') or []
            for inv_c in cached_invs:
                if str(inv_c.get('id')) == str(invitation_id):
                    inv_c['status'] = 'accepted'
            session['invitations_cache'] = cached_invs
            session.modified = True
        except Exception:
            pass

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

        try:
            cached_invs = session.get('invitations_cache') or []
            for inv_c in cached_invs:
                if str(inv_c.get('id')) == str(invitation_id):
                    inv_c['status'] = 'declined'
            session['invitations_cache'] = cached_invs
            session.modified = True
        except Exception:
            pass

        log_event('invitation_declined', actor_id=user_id, target_type='invitation', target_id=invitation_id,
                  metadata={'project_id': invitation['project_id']})

        flash('Invitation declined.', 'info')

    return redirect(request.referrer or url_for('invitations.list_invitations'))


@invitations_bp.route('/invitations/applications/<int:app_id>/review', methods=['POST'])
@login_required
def review_application_alias(app_id):
    """Direct alias for reviewing join requests from invitations page."""
    app_record = query_db("SELECT * FROM project_applications WHERE id = ?", (app_id,), one=True)
    if not app_record:
        flash('Application not found.', 'danger')
        return redirect(url_for('invitations.list_invitations'))
    from app.routes.projects import review_application
    return review_application(app_record['project_id'], app_id)

