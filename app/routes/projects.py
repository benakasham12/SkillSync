"""
Projects management routes implementing PRD FR-05, FR-06, FR-07, FR-08, FR-09, FR-11.
Manages project lifecycle, skill requirements, deterministic candidate ranking, and skill coverage.
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db
from app.routes.auth import login_required
from app.matching import calculate_matches_for_project, compute_team_skill_coverage
from app.analytics import log_event

projects_bp = Blueprint('projects', __name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_BLOCKS = [
    "Morning (9AM-12PM)",
    "Afternoon (1PM-4PM)",
    "Evening (5PM-8PM)",
    "Night (8PM-11PM)"
]


@projects_bp.route('/')
@projects_bp.route('/projects')
def list_projects():
    """List open and published projects, along with current user's owned projects."""
    user_id = session.get('user_id')
    course_filter = request.args.get('course', '').strip()
    skill_filter = request.args.get('skill', '').strip()
    search_q = request.args.get('q', '').strip()

    sql = """
        SELECT p.*, sp.display_name as owner_name, sp.branch as owner_branch, sp.year as owner_year,
               (SELECT COUNT(*) FROM team_members WHERE project_id = p.id) + 1 as current_team_count
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE (p.status = 'published' OR p.owner_id = ?)
    """
    params = [user_id if user_id else -1]

    if course_filter:
        sql += " AND p.course_context LIKE ?"
        params.append(f"%{course_filter}%")
    if search_q:
        sql += " AND (p.title LIKE ? OR p.description LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%"])

    sql += " ORDER BY p.created_at DESC"
    projects = query_db(sql, params)

    # Attach required skills to each project card
    for p in projects:
        reqs = query_db("""
            SELECT psr.*, s.name as skill_name, s.category as skill_category
            FROM project_skill_requirements psr
            JOIN skills s ON psr.skill_id = s.id
            WHERE psr.project_id = ?
        """, (p['id'],))
        p['requirements'] = reqs

    # Filter by skill in python if requested
    if skill_filter:
        projects = [p for p in projects if any(r['skill_name'].lower() == skill_filter.lower() for r in p['requirements'])]

    all_skills = query_db("SELECT name FROM skills WHERE active = 1 ORDER BY name")

    return render_template('projects/list.html', projects=projects, all_skills=all_skills, course_filter=course_filter, skill_filter=skill_filter, search_q=search_q)


@projects_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    user_id = session['user_id']

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        course_context = request.form.get('course_context', 'Innovation & Design Thinking (IDT)').strip()
        team_size_min = int(request.form.get('team_size_min', 2))
        team_size_max = int(request.form.get('team_size_max', 4))
        schedule_notes = request.form.get('schedule_notes', '').strip()

        if not title:
            flash('Project title is required.', 'danger')
            return render_template('projects/create.html')

        if team_size_min < 1 or team_size_max < team_size_min:
            flash('Invalid team size limits.', 'danger')
            return render_template('projects/create.html')

        proj_id = execute_db("""
            INSERT INTO projects (owner_id, title, description, course_context, team_size_min, team_size_max, schedule_notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
        """, (user_id, title, description, course_context, team_size_min, team_size_max, schedule_notes))

        # Add project desired schedule slots
        selected_slots = request.form.getlist('slots')
        for slot_str in selected_slots:
            if '|' in slot_str:
                day, block = slot_str.split('|', 1)
                execute_db("INSERT INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, ?, ?)", (proj_id, day, block))

        # Add project interests
        selected_interests = request.form.getlist('interest_ids')
        for iid in selected_interests:
            execute_db("INSERT INTO project_interests (project_id, interest_id) VALUES (?, ?)", (proj_id, int(iid)))

        log_event('project_created', actor_id=user_id, target_type='project', target_id=proj_id)
        flash('Project created in draft mode! Now add required skills before publishing.', 'success')
        return redirect(url_for('projects.project_detail', project_id=proj_id))

    all_interests = query_db("SELECT * FROM interests ORDER BY category, name")
    return render_template('projects/create.html', all_interests=all_interests, days=DAYS, time_blocks=TIME_BLOCKS)


@projects_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    """Detailed project view showing requirements, team members, pending invitations and live skill coverage."""
    user_id = session.get('user_id')
    project = query_db("SELECT p.*, sp.display_name as owner_name, sp.bio as owner_bio, sp.branch as owner_branch, sp.year as owner_year, u.email as owner_email "
                       "FROM projects p "
                       "JOIN users u ON p.owner_id = u.id "
                       "JOIN student_profiles sp ON u.id = sp.user_id "
                       "WHERE p.id = ?", (project_id,), one=True)
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    is_owner = (user_id == project['owner_id'])

    # Compute skill coverage
    coverage = compute_team_skill_coverage(project_id)

    # Pending invitations for this project (visible to owner)
    pending_invites = []
    if is_owner:
        pending_invites = query_db("""
            SELECT inv.*, sp.display_name as invitee_name, sp.usn as invitee_usn, sp.branch, sp.year, sp.section
            FROM invitations inv
            JOIN users u ON inv.invitee_id = u.id
            JOIN student_profiles sp ON u.id = sp.user_id
            WHERE inv.project_id = ? AND inv.status = 'pending'
            ORDER BY inv.created_at DESC
        """, (project_id,))

    # Desired schedule slots
    slots = query_db("SELECT day_of_week, time_block FROM project_availability_slots WHERE project_id = ?", (project_id,))

    # Project interests
    interests = query_db("""
        SELECT i.name FROM project_interests pi
        JOIN interests i ON pi.interest_id = i.id
        WHERE pi.project_id = ?
    """, (project_id,))

    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")

    return render_template(
        'projects/detail.html',
        project=project,
        is_owner=is_owner,
        coverage=coverage,
        pending_invites=pending_invites,
        slots=slots,
        interests=interests,
        all_skills=all_skills
    )


@projects_bp.route('/projects/<int:project_id>/requirements', methods=['POST'])
@login_required
def update_requirements(project_id):
    """Add or remove skill requirement for project (FR-06)."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    action = request.form.get('action')

    if action == 'add':
        skill_id = request.form.get('skill_id')
        priority = request.form.get('priority', 'must-have')
        # Default weights: must-have = 3.0, preferred = 1.0 (or user custom)
        custom_weight = request.form.get('weight')
        weight = float(custom_weight) if custom_weight else (3.0 if priority == 'must-have' else 1.0)

        if skill_id:
            execute_db("""
                INSERT OR REPLACE INTO project_skill_requirements (project_id, skill_id, priority, weight)
                VALUES (?, ?, ?, ?)
            """, (project_id, int(skill_id), priority, weight))
            flash('Required skill added.', 'success')

    elif action == 'remove':
        skill_id = request.form.get('skill_id')
        if skill_id:
            execute_db("DELETE FROM project_skill_requirements WHERE project_id = ? AND skill_id = ?", (project_id, int(skill_id)))
            flash('Required skill removed.', 'info')

    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/publish', methods=['POST'])
@login_required
def publish_project(project_id):
    """Publish draft project (FR-05 & FR-06). Validates that at least 1 required skill exists."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # FR-06 Acceptance Criteria: Empty requirements cannot be published.
    req_cnt = query_db("SELECT COUNT(*) as cnt FROM project_skill_requirements WHERE project_id = ?", (project_id,), one=True)['cnt']
    if req_cnt == 0:
        flash('Cannot publish project: You must declare at least one required skill first.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    execute_db("UPDATE projects SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    log_event('project_published', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Project published! Classmates can now discover it and match recommendations are active.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/close', methods=['POST'])
@login_required
def close_project(project_id):
    """Close project when team formation is complete (FR-05)."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    execute_db("UPDATE projects SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    log_event('project_closed', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Project closed. Team is now finalized.', 'info')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/matches')
@login_required
def match_candidates(project_id):
    """
    Ranks candidates using explainable formula:
    Match Score = 0.65 * Skill + 0.25 * Availability + 0.10 * Interest
    Supports filtering by skill, section, min_score, and fills_gap_only.
    """
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Only the project owner can view match recommendations for this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # Extract filters (FR-09)
    filters = {
        'skill_id': request.args.get('skill_id'),
        'branch': request.args.get('branch'),
        'year': request.args.get('year'),
        'section': request.args.get('section'),
        'min_score': request.args.get('min_score'),
        'fills_gap_only': request.args.get('fills_gap_only') == '1'
    }

    candidates = calculate_matches_for_project(project_id, filters=filters)
    coverage = compute_team_skill_coverage(project_id)

    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")

    log_event('match_list_viewed', actor_id=user_id, target_type='project', target_id=project_id, metadata={'results_count': len(candidates)})

    return render_template(
        'projects/matches.html',
        project=project,
        candidates=candidates,
        coverage=coverage,
        filters=filters,
        all_skills=all_skills
    )


@projects_bp.route('/api/projects/<int:project_id>/matches')
@login_required
def api_matches(project_id):
    """JSON API endpoint for matches."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    filters = {
        'skill_id': request.args.get('skill_id'),
        'branch': request.args.get('branch'),
        'year': request.args.get('year'),
        'section': request.args.get('section'),
        'min_score': request.args.get('min_score'),
        'fills_gap_only': request.args.get('fills_gap_only') == '1'
    }

    candidates = calculate_matches_for_project(project_id, filters=filters)
    return jsonify({'project_id': project_id, 'matches': candidates})


@projects_bp.route('/api/projects/<int:project_id>/team')
def api_team(project_id):
    """JSON API endpoint for team skill coverage."""
    cov = compute_team_skill_coverage(project_id)
    if not cov:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(cov)
