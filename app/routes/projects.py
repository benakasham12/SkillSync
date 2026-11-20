"""
Projects management routes implementing complete Project Creation and Management System:
- Multi-step project creation and draft persistence
- Required skills specification (Must-Have vs Nice-to-Have, proficiency levels, custom skills)
- Active projects listing with category filters, search, and dynamic status badges
- Project details overview, team configuration, and real-time skill coverage
- Student application workflow (apply, withdraw, accept, reject)
- "My Projects" dashboard for published, drafts, and closed projects
- Deterministic candidate ranking and skill coverage analysis
"""

import json
from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
from app.models import query_db, execute_db
from app.routes.auth import login_required
from app.matching import calculate_matches_for_project, compute_team_skill_coverage
from app.analytics import log_event

projects_bp = Blueprint('projects', __name__)

PROJECT_CATEGORIES = [
    'Web Development',
    'App Development',
    'Artificial Intelligence',
    'Machine Learning',
    'Data Science',
    'IoT & Hardware',
    'Cybersecurity',
    'Cloud Computing',
    'Other'
]

PROJECT_DURATIONS = [
    '1–2 Weeks',
    '1 Month',
    '2–3 Months',
    '3–6 Months',
    'More than 6 Months'
]

COLLABORATION_MODES = ['Online', 'Offline', 'Hybrid']
AVAILABILITY_OPTIONS = ['Weekdays', 'Weekends', 'Flexible']
PROFICIENCY_LEVELS = ['Beginner', 'Intermediate', 'Advanced', 'Expert']
REQUIREMENT_TYPES = ['Must Have', 'Nice to Have']

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_BLOCKS = [
    "Morning (9AM-12PM)",
    "Afternoon (1PM-4PM)",
    "Evening (5PM-8PM)",
    "Night (8PM-11PM)"
]


def get_project_team_count(project_id, owner_id):
    """Return distinct team member count including the project creator."""
    res = query_db("""
        SELECT COUNT(DISTINCT uid) as cnt FROM (
            SELECT ? as uid
            UNION
            SELECT user_id as uid FROM team_members WHERE project_id = ?
        )
    """, (owner_id, project_id), one=True)
    return res['cnt'] if res else 1


def parse_submitted_skills(form):
    """Parse skill requirements from either JSON payload or multi-field inputs."""
    skills_data = []

    # 1. Check if sent as JSON from dynamic UI
    skills_json = form.get('skills_json')
    if skills_json:
        try:
            parsed = json.loads(skills_json)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and item.get('name'):
                        skills_data.append({
                            'name': str(item['name']).strip(),
                            'priority': str(item.get('priority', 'must-have')).strip(),
                            'proficiency': str(item.get('proficiency', 'Intermediate')).strip()
                        })
        except Exception:
            pass

    # 2. Check if sent as standard multi-field inputs
    if not skills_data:
        names = form.getlist('skill_name') or form.getlist('skill_names[]')
        priorities = form.getlist('skill_priority') or form.getlist('skill_priorities[]')
        proficiencies = form.getlist('skill_proficiency') or form.getlist('skill_proficiencies[]')

        for i, name in enumerate(names):
            clean_name = name.strip()
            if clean_name:
                prio = priorities[i].strip() if i < len(priorities) else 'must-have'
                prof = proficiencies[i].strip() if i < len(proficiencies) else 'Intermediate'
                skills_data.append({
                    'name': clean_name,
                    'priority': prio,
                    'proficiency': prof
                })

    return skills_data


def save_project_skills(project_id, skills_data, project_category='Other'):
    """Save or update skill requirements for a project, creating catalog skills as needed."""
    execute_db("DELETE FROM project_skill_requirements WHERE project_id = ?", (project_id,))
    seen = set()
    for item in skills_data:
        name = item.get('name', '').strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())

        priority_raw = item.get('priority', 'must-have').strip().lower()
        if priority_raw in ['must have', 'must-have', 'must_have']:
            priority = 'must-have'
            weight = 3.0
        else:
            priority = 'preferred'
            weight = 1.0

        proficiency = item.get('proficiency', 'Intermediate').strip().capitalize()
        if proficiency not in ['Beginner', 'Intermediate', 'Advanced', 'Expert']:
            proficiency = 'Intermediate'

        skill_row = query_db("SELECT id FROM skills WHERE LOWER(name) = LOWER(?)", (name,), one=True)
        if skill_row:
            skill_id = skill_row['id']
        else:
            skill_id = execute_db("INSERT INTO skills (name, category, active) VALUES (?, ?, 1)", (name, project_category or 'Tools'))

        execute_db("""
            INSERT OR REPLACE INTO project_skill_requirements (project_id, skill_id, priority, proficiency_level, weight)
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, skill_id, priority, proficiency, weight))


@projects_bp.route('/')
def landing():
    """Renders the modern SkillSync opening landing page."""
    try:
        featured_projects = query_db("""
            SELECT p.*, sp.display_name as owner_name, sp.branch as owner_branch, sp.year as owner_year,
                   (SELECT COUNT(*) FROM team_members WHERE project_id = p.id) + 1 as current_team_count
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            JOIN student_profiles sp ON u.id = sp.user_id
            WHERE p.status = 'published'
            ORDER BY p.created_at DESC
            LIMIT 3
        """)

        for p in featured_projects:
            reqs = query_db("""
                SELECT psr.*, s.name as skill_name, s.category as skill_category
                FROM project_skill_requirements psr
                JOIN skills s ON psr.skill_id = s.id
                WHERE psr.project_id = ?
            """, (p['id'],))
            p['requirements'] = reqs

        total_projects = query_db("SELECT COUNT(*) as count FROM projects WHERE status = 'published'", one=True)
        total_skills = query_db("SELECT COUNT(*) as count FROM skills", one=True)
        total_students = query_db("SELECT COUNT(*) as count FROM student_profiles WHERE is_match_ready = 1", one=True)

        stats = {
            'projects_count': total_projects['count'] if total_projects else 0,
            'skills_count': total_skills['count'] if total_skills else 0,
            'students_count': total_students['count'] if total_students else 0
        }
    except Exception:
        featured_projects = []
        stats = {'projects_count': 0, 'skills_count': 0, 'students_count': 0}

    return render_template('landing.html', featured_projects=featured_projects, stats=stats)


@projects_bp.route('/about-skillsync')
def about_skillsync():
    """Renders the dedicated Introduction to SkillSync page presenting core pillars and capabilities."""
    return render_template('about_skillsync.html')


@projects_bp.route('/features')
def features():
    """Renders the dedicated Features page."""
    return render_template('features.html')


@projects_bp.route('/how-it-works')
def how_it_works():
    """Renders the dedicated How It Works page."""
    return render_template('how_it_works.html')


@projects_bp.route('/bmsit-engineering')
def bmsit_engineering():
    """Renders the dedicated Built for BMSIT & M Engineering page."""
    return render_template('bmsit_engineering.html')


@projects_bp.route('/about')
def about():
    """Renders the dedicated Built for BMSIT & M Engineering page (aliased for /about)."""
    return render_template('bmsit_engineering.html')


@projects_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Renders the dedicated Contact page and handles message inquiries."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()

        if not name or not email or not message:
            flash('Please complete all required fields (Name, Email, and Message).', 'danger')
        else:
            flash('Thank you for reaching out! The SkillSync engineering team has received your message.', 'success')
            return redirect(url_for('projects.contact'))

    return render_template('contact.html')


@projects_bp.route('/projects')
def list_projects():
    """List open and published projects, with filters, search, and dynamic status."""
    user_id = session.get('user_id')
    course_filter = request.args.get('course', '').strip()
    category_filter = request.args.get('category', '').strip()
    skill_filter = request.args.get('skill', '').strip()
    search_q = request.args.get('q', '').strip()
    tab_filter = request.args.get('tab', 'all').strip()

    sql = """
        SELECT p.*, sp.display_name as owner_name, sp.branch as owner_branch, sp.year as owner_year, sp.bio as owner_bio,
               u.email as owner_email,
               (SELECT COUNT(DISTINCT uid) FROM (
                   SELECT p.owner_id as uid
                   UNION
                   SELECT user_id as uid FROM team_members WHERE project_id = p.id
               )) as current_team_count
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE (p.status = 'published' OR p.owner_id = ?)
    """
    params = [user_id if user_id else -1]

    if tab_filter == 'seeking':
        sql += " AND p.status = 'published' AND ((SELECT COUNT(DISTINCT uid) FROM (SELECT p.owner_id as uid UNION SELECT user_id as uid FROM team_members WHERE project_id = p.id)) < p.team_size_max)"
    elif tab_filter == 'my' and user_id:
        sql += " AND p.owner_id = ?"
        params.append(user_id)

    if category_filter:
        sql += " AND p.category = ?"
        params.append(category_filter)
    if course_filter:
        sql += " AND p.course_context LIKE ?"
        params.append(f"%{course_filter}%")
    if search_q:
        sql += " AND (p.title LIKE ? OR p.description LIKE ? OR p.technologies LIKE ?)"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])

    sql += " ORDER BY p.created_at DESC"
    projects = query_db(sql, params)

    # Attach required skills and user application status to each project card
    for p in projects:
        reqs = query_db("""
            SELECT psr.*, s.name as skill_name, s.category as skill_category
            FROM project_skill_requirements psr
            JOIN skills s ON psr.skill_id = s.id
            WHERE psr.project_id = ?
            ORDER BY psr.weight DESC, s.name ASC
        """, (p['id'],))
        p['requirements'] = reqs
        p['available_positions'] = max(0, p['team_size_max'] - p['current_team_count'])

        # Split technologies string into list
        if p.get('technologies'):
            p['tech_list'] = [t.strip() for t in p['technologies'].split(',') if t.strip()]
        else:
            p['tech_list'] = []

        # Check if user has an application or is a member
        p['user_application'] = None
        p['is_team_member'] = False
        if user_id:
            if user_id == p['owner_id']:
                p['is_team_member'] = True
            else:
                mem = query_db("SELECT 1 FROM team_members WHERE project_id = ? AND user_id = ?", (p['id'], user_id), one=True)
                if mem:
                    p['is_team_member'] = True
                else:
                    app_record = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (p['id'], user_id), one=True)
                    p['user_application'] = app_record

    # Filter by skill in python if requested
    if skill_filter:
        projects = [p for p in projects if any(r['skill_name'].lower() == skill_filter.lower() for r in p['requirements'])]

    all_skills = query_db("SELECT name FROM skills WHERE active = 1 ORDER BY name")

    return render_template(
        'projects/list.html',
        projects=projects,
        all_skills=all_skills,
        categories=PROJECT_CATEGORIES,
        course_filter=course_filter,
        category_filter=category_filter,
        skill_filter=skill_filter,
        search_q=search_q,
        tab_filter=tab_filter
    )


@projects_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create_project():
    """Create a new course project with multi-step support, skills requirements, and draft/publish actions."""
    user_id = session['user_id']

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Web Development').strip()
        objectives = request.form.get('objectives', '').strip()
        technologies = request.form.get('technologies', '').strip()
        duration = request.form.get('duration', '2–3 Months').strip()
        collaboration_mode = request.form.get('collaboration_mode', 'Hybrid').strip()
        availability = request.form.get('availability', 'Flexible').strip()
        additional_requirements = request.form.get('additional_requirements', '').strip()
        course_context = request.form.get('course_context', 'Innovation & Design Thinking (IDT)').strip()

        # Team size
        team_size_max_input = request.form.get('team_size_max', '4').strip()
        if team_size_max_input == 'custom':
            try:
                team_size_max = int(request.form.get('custom_team_size', 4))
            except (ValueError, TypeError):
                team_size_max = 4
        else:
            try:
                team_size_max = int(team_size_max_input)
            except (ValueError, TypeError):
                team_size_max = 4
        team_size_max = max(2, min(20, team_size_max))
        team_size_min = int(request.form.get('team_size_min', 2))
        schedule_notes = request.form.get('schedule_notes', availability).strip()

        action = request.form.get('action', 'publish')
        skills_data = parse_submitted_skills(request.form)

        # Validation for Publish
        if action == 'publish':
            if not title:
                flash('Project name is required to publish.', 'danger')
                return render_template(
                    'projects/create.html',
                    categories=PROJECT_CATEGORIES,
                    durations=PROJECT_DURATIONS,
                    collaboration_modes=COLLABORATION_MODES,
                    availabilities=AVAILABILITY_OPTIONS,
                    proficiencies=PROFICIENCY_LEVELS,
                    all_skills=query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name"),
                    all_interests=query_db("SELECT * FROM interests ORDER BY category, name"),
                    days=DAYS,
                    time_blocks=TIME_BLOCKS
                )
            if not description:
                flash('Project description is required to publish.', 'danger')
                return render_template(
                    'projects/create.html',
                    categories=PROJECT_CATEGORIES,
                    durations=PROJECT_DURATIONS,
                    collaboration_modes=COLLABORATION_MODES,
                    availabilities=AVAILABILITY_OPTIONS,
                    proficiencies=PROFICIENCY_LEVELS,
                    all_skills=query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name"),
                    all_interests=query_db("SELECT * FROM interests ORDER BY category, name"),
                    days=DAYS,
                    time_blocks=TIME_BLOCKS
                )
            if not skills_data:
                flash('Cannot publish project: You must declare at least one required skill before publishing.', 'danger')
                return render_template(
                    'projects/create.html',
                    categories=PROJECT_CATEGORIES,
                    durations=PROJECT_DURATIONS,
                    collaboration_modes=COLLABORATION_MODES,
                    availabilities=AVAILABILITY_OPTIONS,
                    proficiencies=PROFICIENCY_LEVELS,
                    all_skills=query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name"),
                    all_interests=query_db("SELECT * FROM interests ORDER BY category, name"),
                    days=DAYS,
                    time_blocks=TIME_BLOCKS
                )
            status = 'published'
        else:
            # Save as Draft
            if not title:
                title = 'Untitled Project (Draft)'
            status = 'draft'

        proj_id = execute_db("""
            INSERT INTO projects (
                owner_id, title, description, category, objectives, technologies,
                duration, collaboration_mode, availability, additional_requirements,
                course_context, team_size_min, team_size_max, schedule_notes, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, title, description, category, objectives, technologies,
            duration, collaboration_mode, availability, additional_requirements,
            course_context, team_size_min, team_size_max, schedule_notes, status
        ))

        # Add creator to team_members
        execute_db("""
            INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'owner', CURRENT_TIMESTAMP)
        """, (proj_id, user_id))

        # Initialize project group chat
        from app.routes.messages import get_or_create_project_group
        get_or_create_project_group(proj_id)

        # Save required skills
        save_project_skills(proj_id, skills_data, category)

        # Desired schedule slots
        selected_slots = request.form.getlist('slots')
        for slot_str in selected_slots:
            if '|' in slot_str:
                day, block = slot_str.split('|', 1)
                execute_db("INSERT OR IGNORE INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, ?, ?)", (proj_id, day, block))

        # Project interests
        selected_interests = request.form.getlist('interest_ids')
        for iid in selected_interests:
            try:
                execute_db("INSERT OR IGNORE INTO project_interests (project_id, interest_id) VALUES (?, ?)", (proj_id, int(iid)))
            except Exception:
                pass

        if status == 'published':
            log_event('project_published', actor_id=user_id, target_type='project', target_id=proj_id)
            flash('Project published successfully! It is now visible in Active Projects seeking teammates.', 'success')
        else:
            log_event('project_created', actor_id=user_id, target_type='project', target_id=proj_id)
            flash('Project saved as draft! Only you can view and edit it until you publish.', 'info')

        return redirect(url_for('projects.project_detail', project_id=proj_id))

    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")
    all_interests = query_db("SELECT * FROM interests ORDER BY category, name")
    return render_template(
        'projects/create.html',
        categories=PROJECT_CATEGORIES,
        durations=PROJECT_DURATIONS,
        collaboration_modes=COLLABORATION_MODES,
        availabilities=AVAILABILITY_OPTIONS,
        proficiencies=PROFICIENCY_LEVELS,
        all_skills=all_skills,
        all_interests=all_interests,
        days=DAYS,
        time_blocks=TIME_BLOCKS
    )


@projects_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    """Edit project information, team size, and skill requirements."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized: You can only edit projects you created.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Web Development').strip()
        objectives = request.form.get('objectives', '').strip()
        technologies = request.form.get('technologies', '').strip()
        duration = request.form.get('duration', '2–3 Months').strip()
        collaboration_mode = request.form.get('collaboration_mode', 'Hybrid').strip()
        availability = request.form.get('availability', 'Flexible').strip()
        additional_requirements = request.form.get('additional_requirements', '').strip()
        course_context = request.form.get('course_context', project['course_context']).strip()

        # Team size
        team_size_max_input = request.form.get('team_size_max', str(project['team_size_max'])).strip()
        if team_size_max_input == 'custom':
            try:
                team_size_max = int(request.form.get('custom_team_size', 4))
            except (ValueError, TypeError):
                team_size_max = 4
        else:
            try:
                team_size_max = int(team_size_max_input)
            except (ValueError, TypeError):
                team_size_max = 4
        team_size_max = max(2, min(20, team_size_max))
        team_size_min = int(request.form.get('team_size_min', 2))
        schedule_notes = request.form.get('schedule_notes', availability).strip()

        action = request.form.get('action', 'save')
        skills_data = parse_submitted_skills(request.form)

        if action == 'publish':
            if not title or not description:
                flash('Title and description are required to publish.', 'danger')
                return redirect(url_for('projects.edit_project', project_id=project_id))
            if not skills_data:
                flash('Cannot publish project: You must declare at least one required skill first.', 'danger')
                return redirect(url_for('projects.edit_project', project_id=project_id))
            status = 'published'
        elif action == 'draft':
            status = 'draft'
        else:
            status = project['status']

        execute_db("""
            UPDATE projects SET
                title = ?, description = ?, category = ?, objectives = ?, technologies = ?,
                duration = ?, collaboration_mode = ?, availability = ?, additional_requirements = ?,
                course_context = ?, team_size_min = ?, team_size_max = ?, schedule_notes = ?,
                status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            title, description, category, objectives, technologies,
            duration, collaboration_mode, availability, additional_requirements,
            course_context, team_size_min, team_size_max, schedule_notes,
            status, project_id
        ))

        if skills_data:
            save_project_skills(project_id, skills_data, category)

        flash('Project updated successfully.', 'success')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    current_skills = query_db("""
        SELECT psr.*, s.name as skill_name, s.category as skill_category
        FROM project_skill_requirements psr
        JOIN skills s ON psr.skill_id = s.id
        WHERE psr.project_id = ?
        ORDER BY psr.weight DESC, s.name ASC
    """, (project_id,))

    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")
    return render_template(
        'projects/edit.html',
        project=project,
        current_skills=current_skills,
        categories=PROJECT_CATEGORIES,
        durations=PROJECT_DURATIONS,
        collaboration_modes=COLLABORATION_MODES,
        availabilities=AVAILABILITY_OPTIONS,
        proficiencies=PROFICIENCY_LEVELS,
        all_skills=all_skills
    )


@projects_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Delete a project and its associated requirements and applications."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized: Only the project creator can delete this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

    execute_db("DELETE FROM projects WHERE id = ?", (project_id,))
    log_event('project_deleted', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Project and all associated records deleted successfully.', 'info')
    return redirect(url_for('projects.my_projects'))


@projects_bp.route('/projects/<int:project_id>')
def project_detail(project_id):
    """Detailed project view showing overview, team members, applications, and coverage."""
    user_id = session.get('user_id')
    project = query_db("""
        SELECT p.*, sp.display_name as owner_name, sp.bio as owner_bio, sp.branch as owner_branch,
               sp.year as owner_year, sp.usn as owner_usn, sp.section as owner_section,
               sp.institution as owner_institution, u.email as owner_email
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE p.id = ?
    """, (project_id,), one=True)

    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    is_owner = (user_id == project['owner_id'])

    # Team count and members
    current_team_count = get_project_team_count(project_id, project['owner_id'])
    available_positions = max(0, project['team_size_max'] - current_team_count)

    # Accepted team members
    team_members_list = query_db("""
        SELECT tm.*, sp.display_name, sp.branch, sp.year, sp.section, sp.bio, u.email
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE tm.project_id = ? AND tm.role != 'owner'
        ORDER BY tm.joined_at ASC
    """, (project_id,))

    # Split technologies
    if project.get('technologies'):
        tech_list = [t.strip() for t in project['technologies'].split(',') if t.strip()]
    else:
        tech_list = []

    # Required skills
    requirements = query_db("""
        SELECT psr.*, s.name as skill_name, s.category as skill_category
        FROM project_skill_requirements psr
        JOIN skills s ON psr.skill_id = s.id
        WHERE psr.project_id = ?
        ORDER BY psr.weight DESC, s.name ASC
    """, (project_id,))

    must_have_skills = [r for r in requirements if r['priority'] in ['must-have', 'Must Have', 'must_have']]
    nice_to_have_skills = [r for r in requirements if r['priority'] not in ['must-have', 'Must Have', 'must_have']]

    # Compute coverage
    coverage = compute_team_skill_coverage(project_id)

    # Applications
    applications = []
    user_application = None
    is_team_member = is_owner or any(m['user_id'] == user_id for m in team_members_list)

    if user_id:
        if is_owner:
            applications = query_db("""
                SELECT pa.*, sp.display_name as applicant_name, sp.branch as applicant_branch,
                       sp.year as applicant_year, sp.section as applicant_section, sp.bio as applicant_bio,
                       u.email as applicant_email
                FROM project_applications pa
                JOIN users u ON pa.applicant_id = u.id
                JOIN student_profiles sp ON u.id = sp.user_id
                WHERE pa.project_id = ?
                ORDER BY CASE pa.application_status WHEN 'pending' THEN 1 ELSE 2 END, pa.created_at DESC
            """, (project_id,))
        else:
            user_application = query_db("""
                SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?
            """, (project_id, user_id), one=True)

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

    slots = query_db("SELECT day_of_week, time_block FROM project_availability_slots WHERE project_id = ?", (project_id,))
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
        is_team_member=is_team_member,
        current_team_count=current_team_count,
        available_positions=available_positions,
        team_members_list=team_members_list,
        tech_list=tech_list,
        must_have_skills=must_have_skills,
        nice_to_have_skills=nice_to_have_skills,
        coverage=coverage,
        applications=applications,
        user_application=user_application,
        pending_invites=pending_invites,
        slots=slots,
        interests=interests,
        all_skills=all_skills
    )


@projects_bp.route('/projects/<int:project_id>/apply', methods=['POST'])
@login_required
def apply_project(project_id):
    """Submit an application to join a published project."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if project['status'] != 'published':
        flash('This project is not currently accepting applications.', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    if project['owner_id'] == user_id:
        flash('You are the creator of this project and cannot apply to join it.', 'warning')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    already_member = query_db("SELECT 1 FROM team_members WHERE project_id = ? AND user_id = ?", (project_id, user_id), one=True)
    if already_member:
        flash('You are already an accepted member of this project team.', 'info')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    current_team_count = get_project_team_count(project_id, project['owner_id'])
    if current_team_count >= project['team_size_max']:
        flash('This project team has reached its maximum size and is full.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    introduction = request.form.get('introduction', '').strip()

    existing_app = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (project_id, user_id), one=True)
    if existing_app:
        if existing_app['application_status'] == 'pending':
            flash('You have already applied to this project. Your application is currently pending review.', 'warning')
            return redirect(url_for('projects.project_detail', project_id=project_id))
        elif existing_app['application_status'] == 'accepted':
            flash('Your application has already been accepted.', 'info')
            return redirect(url_for('projects.project_detail', project_id=project_id))
        else:
            execute_db("""
                UPDATE project_applications SET
                    introduction = ?, application_status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (introduction, existing_app['id']))
            flash('Your application has been resubmitted successfully!', 'success')
            return redirect(url_for('projects.project_detail', project_id=project_id))

    execute_db("""
        INSERT INTO project_applications (project_id, applicant_id, introduction, application_status)
        VALUES (?, ?, ?, 'pending')
    """, (project_id, user_id, introduction))

    log_event('project_application_sent', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Application sent successfully! The project creator will review your profile.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/applications/<int:app_id>/withdraw', methods=['POST'])
@login_required
def withdraw_application(app_id):
    """Withdraw an application sent by the current student."""
    user_id = session['user_id']
    app_record = query_db("SELECT * FROM project_applications WHERE id = ?", (app_id,), one=True)
    if not app_record or app_record['applicant_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.my_projects'))

    execute_db("UPDATE project_applications SET application_status = 'withdrawn', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (app_id,))
    flash('Application withdrawn successfully.', 'info')
    return redirect(request.referrer or url_for('projects.my_projects'))


@projects_bp.route('/projects/<int:project_id>/applications/<int:app_id>/review', methods=['POST'])
@login_required
def review_application(project_id, app_id):
    """Accept or reject an application submitted by a student."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized: Only project creators can review applications.', 'danger')
        return redirect(url_for('projects.list_projects'))

    app_record = query_db("SELECT * FROM project_applications WHERE id = ? AND project_id = ?", (app_id, project_id), one=True)
    if not app_record:
        flash('Application not found.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    decision = request.form.get('decision', '').strip().lower()

    if decision == 'accept':
        current_team_count = get_project_team_count(project_id, user_id)
        if current_team_count >= project['team_size_max']:
            flash('Cannot accept application: The project team is already full.', 'danger')
            return redirect(url_for('projects.project_detail', project_id=project_id))

        execute_db("""
            INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
            VALUES (?, ?, 'member', CURRENT_TIMESTAMP)
        """, (project_id, app_record['applicant_id']))

        execute_db("""
            UPDATE project_applications SET application_status = 'accepted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (app_id,))

        # Add to project group chat
        from app.routes.messages import add_student_to_project_group
        add_student_to_project_group(project_id, app_record['applicant_id'])

        log_event('application_accepted', actor_id=user_id, target_type='application', target_id=app_id)
        flash('Application accepted! Student has been added to the team roster.', 'success')

    elif decision == 'reject':
        execute_db("""
            UPDATE project_applications SET application_status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (app_id,))
        log_event('application_rejected', actor_id=user_id, target_type='application', target_id=app_id)
        flash('Application declined.', 'info')

    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_team_member(project_id, member_id):
    """Remove an accepted team member from the project."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if member_id == project['owner_id']:
        flash('The project owner cannot be removed from the team.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    execute_db("DELETE FROM team_members WHERE project_id = ? AND user_id = ?", (project_id, member_id))
    execute_db("UPDATE project_applications SET application_status = 'withdrawn' WHERE project_id = ? AND applicant_id = ?", (project_id, member_id))

    # Revoke group chat access
    from app.routes.messages import remove_student_from_project_group
    remove_student_from_project_group(project_id, member_id)

    flash('Team member removed from the project.', 'info')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/my-projects')
@login_required
def my_projects():
    """Project management dashboard displaying created projects and submitted applications."""
    user_id = session['user_id']

    my_proj_list = query_db("""
        SELECT p.*,
               (SELECT COUNT(DISTINCT uid) FROM (
                   SELECT p.owner_id as uid
                   UNION
                   SELECT user_id as uid FROM team_members WHERE project_id = p.id
               )) as current_team_count,
               (SELECT COUNT(*) FROM project_applications WHERE project_id = p.id AND application_status = 'pending') as pending_apps_count
        FROM projects p
        WHERE p.owner_id = ?
        ORDER BY p.updated_at DESC
    """, (user_id,))

    for p in my_proj_list:
        p['requirements'] = query_db("""
            SELECT psr.*, s.name as skill_name, s.category as skill_category
            FROM project_skill_requirements psr
            JOIN skills s ON psr.skill_id = s.id
            WHERE psr.project_id = ?
            ORDER BY psr.weight DESC, s.name ASC
        """, (p['id'],))
        p['available_positions'] = max(0, p['team_size_max'] - p['current_team_count'])

    published = [p for p in my_proj_list if p['status'] == 'published']
    drafts = [p for p in my_proj_list if p['status'] == 'draft']
    closed = [p for p in my_proj_list if p['status'] in ['closed', 'archived']]

    my_applications = query_db("""
        SELECT pa.*, p.title as project_title, p.category, p.status as project_status, p.team_size_max,
               sp.display_name as owner_name, sp.branch as owner_branch
        FROM project_applications pa
        JOIN projects p ON pa.project_id = p.id
        JOIN users u ON p.owner_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE pa.applicant_id = ?
        ORDER BY pa.created_at DESC
    """, (user_id,))

    return render_template(
        'projects/my_projects.html',
        published=published,
        drafts=drafts,
        closed=closed,
        my_applications=my_applications
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
        proficiency = request.form.get('proficiency_level', 'Intermediate')
        custom_weight = request.form.get('weight')
        weight = float(custom_weight) if custom_weight else (3.0 if priority in ['must-have', 'Must Have'] else 1.0)

        if skill_id:
            execute_db("""
                INSERT OR REPLACE INTO project_skill_requirements (project_id, skill_id, priority, proficiency_level, weight)
                VALUES (?, ?, ?, ?, ?)
            """, (project_id, int(skill_id), priority, proficiency, weight))
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
    """Publish draft project. Validates that at least 1 required skill exists."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    req_cnt = query_db("SELECT COUNT(*) as cnt FROM project_skill_requirements WHERE project_id = ?", (project_id,), one=True)['cnt']
    if req_cnt == 0:
        flash('Cannot publish project: You must declare at least one required skill first.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project_id))

    execute_db("UPDATE projects SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    log_event('project_published', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Project published! Classmates can now discover it and apply.', 'success')
    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/close', methods=['POST'])
@login_required
def close_project(project_id):
    """Toggle project status between closed and published."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if project['status'] == 'closed':
        execute_db("UPDATE projects SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        flash('Project reopened! Now accepting teammate applications.', 'success')
    else:
        execute_db("UPDATE projects SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        log_event('project_closed', actor_id=user_id, target_type='project', target_id=project_id)
        flash('Project closed. Team is now finalized and no longer accepting applications.', 'info')

    return redirect(url_for('projects.project_detail', project_id=project_id))


@projects_bp.route('/projects/<int:project_id>/matches')
@login_required
def match_candidates(project_id):
    """Ranks candidates using explainable formula: Match Score = 0.65 * Skill + 0.25 * Availability + 0.10 * Interest"""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or project['owner_id'] != user_id:
        flash('Only the project owner can view match recommendations for this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

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
