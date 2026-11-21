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
from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify, has_request_context
from app.models import query_db, execute_db, get_db
from app.routes.auth import login_required
from app.matching import calculate_matches_for_project, compute_team_skill_coverage
from app.analytics import log_event

projects_bp = Blueprint('projects', __name__)

PROJECT_CATEGORIES = [
    'Web Development',
    'App Development',
    'AI / Machine Learning',
    'Data Science',
    'Cybersecurity',
    'UI/UX Design',
    'IoT & Hardware',
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


def is_project_owner(project, user_id=None, db_path=None, allow_admin=True):
    """
    Robust project ownership and admin authorization verification:
    1. Priority Admin & Coordinator Authorization Override (when allow_admin=True):
       Verified administrators and faculty coordinators have unconditional
       authority to manage and edit all platform projects regardless of creator.
    2. Direct match: project['owner_id'] == user_id (with string and integer coercion).
    3. Profile ID resolution:
       - If project['owner_id'] is a student_profiles.id, check if user_id is the profile's user_id.
       - If user_id is a student_profiles.id, check if project['owner_id'] matches its user_id.
    4. Team roster check: checks if team_members has role='owner' for this user and project.
    """
    if user_id is None and has_request_context():
        user_id = session.get('user_id')

    if not user_id and has_request_context():
        auth_hdr = request.headers.get('X-User-Id') or request.headers.get('Authorization', '')
        if auth_hdr:
            token = auth_hdr[7:].strip() if auth_hdr.startswith('Bearer ') else auth_hdr.strip()
            if token.isdigit():
                user_id = int(token)

    if not user_id:
        return False

    u_str = str(user_id).strip()
    try:
        u_int = int(u_str)
    except (ValueError, TypeError):
        u_int = None

    # Step 1: Priority Admin & Coordinator Override
    # Unconditionally grants full access to admins and faculty coordinators
    if allow_admin:
        user_role = session.get('user_role') if has_request_context() else None
        if not user_role and u_int is not None:
            try:
                u_rec = query_db("SELECT role FROM users WHERE id = ?", (u_int,), one=True, db_path=db_path)
                if u_rec and u_rec.get('role'):
                    user_role = u_rec.get('role')
            except Exception:
                pass
        if user_role and str(user_role).strip().lower() in ('admin', 'coordinator'):
            return True

    if not project:
        return False

    if not isinstance(project, dict):
        try:
            pid = int(project)
            project = query_db("SELECT * FROM projects WHERE id = ?", (pid,), one=True, db_path=db_path)
            if not project:
                return False
        except (ValueError, TypeError):
            return False

    owner_val = project.get('owner_id')
    if owner_val is not None:
        o_str = str(owner_val).strip()
        try:
            o_int = int(o_str)
        except (ValueError, TypeError):
            o_int = None

        # Direct string or integer match
        if o_str == u_str or (o_int is not None and u_int is not None and o_int == u_int):
            return True

        # Check if owner_val is student_profiles.id matching user's account
        if u_int is not None:
            prof_by_user = query_db("SELECT id FROM student_profiles WHERE user_id = ?", (u_int,), one=True, db_path=db_path)
            if prof_by_user and str(prof_by_user['id']) == o_str:
                return True

        # Check if user_id is student_profiles.id matching project's owner_id
        if o_int is not None:
            user_by_prof = query_db("SELECT user_id FROM student_profiles WHERE id = ?", (o_int,), one=True, db_path=db_path)
            if user_by_prof and str(user_by_prof['user_id']) == u_str:
                return True

    # Check team_members table for role='owner'
    project_id = project.get('id')
    if project_id:
        p_id = int(project_id)
        owner_member = query_db("""
            SELECT 1 FROM team_members
            WHERE project_id = ?
              AND (
                  user_id = ?
                  OR user_id IN (SELECT id FROM student_profiles WHERE user_id = ?)
                  OR user_id IN (SELECT user_id FROM student_profiles WHERE id = ?)
              )
              AND LOWER(role) = 'owner'
        """, (p_id, u_str, u_str, u_str), one=True, db_path=db_path)
        if owner_member:
            return True

    return False


def parse_submitted_skills(form_data=None, json_data=None):
    """Parse skill requirements from JSON payload, raw skills array, or multi-field inputs."""
    skills_data = []
    form_data = form_data or {}
    json_data = json_data or {}

    def extract_item(item):
        if isinstance(item, str) and item.strip():
            return {
                'name': item.strip(),
                'priority': 'must-have',
                'proficiency': 'Intermediate'
            }
        if isinstance(item, dict):
            s_name = (
                item.get('name')
                or item.get('skill')
                or item.get('skill_name')
                or item.get('skillName')
                or item.get('title')
            )
            if s_name:
                prio = (
                    item.get('priority')
                    or item.get('importance')
                    or item.get('priority_level')
                    or 'must-have'
                )
                prof = (
                    item.get('proficiency')
                    or item.get('proficiency_level')
                    or item.get('level')
                    or 'Intermediate'
                )
                return {
                    'name': str(s_name).strip(),
                    'priority': str(prio).strip(),
                    'proficiency': str(prof).strip()
                }
        return None

    candidate_keys = [
        'skills_json', 'skills', 'required_skills', 'project_skills',
        'skill_requirements', 'skill_list'
    ]
    raw_skills = None
    for k in candidate_keys:
        val = form_data.get(k) or json_data.get(k)
        if val:
            raw_skills = val
            break

    if raw_skills:
        if isinstance(raw_skills, str):
            try:
                parsed = json.loads(raw_skills)
                if isinstance(parsed, list):
                    raw_skills = parsed
            except Exception:
                pass
        if isinstance(raw_skills, list):
            for item in raw_skills:
                extracted = extract_item(item)
                if extracted:
                    skills_data.append(extracted)

    if not skills_data and 'skills' in json_data and isinstance(json_data['skills'], list):
        for item in json_data['skills']:
            extracted = extract_item(item)
            if extracted:
                skills_data.append(extracted)

    if not skills_data and hasattr(form_data, 'getlist'):
        names = form_data.getlist('skill_name') or form_data.getlist('skill_names[]')
        priorities = form_data.getlist('skill_priority') or form_data.getlist('skill_priorities[]')
        proficiencies = form_data.getlist('skill_proficiency') or form_data.getlist('skill_proficiencies[]')

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
            SELECT p.*,
                   COALESCE(sp.display_name, u.email, 'Student') as owner_name,
                   COALESCE(sp.branch, 'CSE') as owner_branch,
                   COALESCE(sp.year, '1st Year') as owner_year,
                   (SELECT COUNT(*) FROM team_members WHERE project_id = p.id) + 1 as current_team_count
            FROM projects p
            LEFT JOIN users u ON (p.owner_id = u.id OR p.owner_id = (SELECT sp2.id FROM student_profiles sp2 WHERE sp2.user_id = u.id))
            LEFT JOIN student_profiles sp ON (sp.user_id = u.id OR sp.id = p.owner_id)
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


def compute_pagination(current_page, total_pages, delta=2):
    """Generates a clean list of page numbers and ellipses for UI pagination."""
    if total_pages <= 7:
        return list(range(1, total_pages + 1))

    pages = []
    left = max(1, current_page - delta)
    right = min(total_pages, current_page + delta)

    if left > 1:
        pages.append(1)
        if left > 2:
            pages.append('...')

    for p in range(left, right + 1):
        pages.append(p)

    if right < total_pages:
        if right < total_pages - 1:
            pages.append('...')
        pages.append(total_pages)

    return pages


@projects_bp.route('/projects')
def list_projects():
    """List open and published projects with smart pagination, search, category filters, and sorting."""
    import math

    user_id = session.get('user_id')
    page = request.args.get('page', 1, type=int)
    if not page or page < 1:
        page = 1
    per_page = 9

    course_filter = request.args.get('course', '').strip()
    category_filter = request.args.get('category', '').strip()
    skill_filter = request.args.get('skill', '').strip()
    search_q = request.args.get('q', '').strip()
    tab_filter = request.args.get('tab', 'all').strip()
    sort_by = request.args.get('sort', 'recent').strip().lower()

    # Build WHERE conditions
    where_clauses = []
    where_params = []

    # 1. Tab / Visibility Filter
    if tab_filter == 'my' and user_id:
        where_clauses.append("""
            (
                p.owner_id = ?
                OR p.owner_id = (SELECT id FROM student_profiles WHERE user_id = ?)
                OR p.owner_id IN (SELECT user_id FROM student_profiles WHERE id = ?)
                OR EXISTS (
                    SELECT 1 FROM team_members tm
                    WHERE tm.project_id = p.id
                      AND LOWER(tm.role) = 'owner'
                      AND (tm.user_id = ? OR tm.user_id = (SELECT id FROM student_profiles WHERE user_id = ?))
                )
            )
        """)
        where_params.extend([user_id, user_id, user_id, user_id, user_id])
    elif tab_filter == 'seeking':
        where_clauses.append("""
            p.status = 'published' AND (
                (SELECT COUNT(DISTINCT uid) FROM (
                    SELECT p.owner_id as uid UNION SELECT user_id as uid FROM team_members WHERE project_id = p.id
                )) < p.team_size_max
            )
        """)
    elif tab_filter == 'completed':
        where_clauses.append("p.status IN ('closed', 'completed', 'archived')")
    else:
        # Default 'all': published projects, plus private drafts owned by current user
        if user_id:
            where_clauses.append("""
                (
                    p.status = 'published'
                    OR p.owner_id = ?
                    OR p.owner_id = (SELECT id FROM student_profiles WHERE user_id = ?)
                    OR p.owner_id IN (SELECT user_id FROM student_profiles WHERE id = ?)
                    OR EXISTS (
                        SELECT 1 FROM team_members tm
                        WHERE tm.project_id = p.id
                          AND LOWER(tm.role) = 'owner'
                          AND (tm.user_id = ? OR tm.user_id = (SELECT id FROM student_profiles WHERE user_id = ?))
                    )
                )
            """)
            where_params.extend([user_id, user_id, user_id, user_id, user_id])
        else:
            where_clauses.append("p.status = 'published'")

    # 2. Category Filter
    if category_filter:
        if category_filter == 'AI / Machine Learning':
            where_clauses.append("p.category IN ('AI / Machine Learning', 'AI & Machine Learning', 'Artificial Intelligence', 'Machine Learning')")
        elif category_filter == 'Other':
            where_clauses.append("""
                (p.category = 'Other' OR p.category NOT IN (
                    'Web Development', 'App Development', 'AI / Machine Learning', 'AI & Machine Learning',
                    'Artificial Intelligence', 'Machine Learning', 'Data Science', 'Cybersecurity',
                    'UI/UX Design', 'IoT & Hardware', 'Cloud Computing'
                ))
            """)
        else:
            where_clauses.append("p.category = ?")
            where_params.append(category_filter)

    # 3. Course Filter
    if course_filter:
        where_clauses.append("p.course_context LIKE ?")
        where_params.append(f"%{course_filter}%")

    # 4. Search Query (name, description, technology stack, skills required, project creator)
    if search_q:
        q_wildcard = f"%{search_q}%"
        where_clauses.append("""
            (
                p.title LIKE ?
                OR p.description LIKE ?
                OR p.technologies LIKE ?
                OR EXISTS (
                    SELECT 1 FROM student_profiles sp_s
                    WHERE (sp_s.user_id = p.owner_id OR sp_s.id = p.owner_id)
                      AND sp_s.display_name LIKE ?
                )
                OR EXISTS (
                    SELECT 1 FROM users u_s
                    WHERE (u_s.id = p.owner_id OR u_s.id IN (SELECT sp_s2.user_id FROM student_profiles sp_s2 WHERE sp_s2.id = p.owner_id))
                      AND u_s.email LIKE ?
                )
                OR EXISTS (
                    SELECT 1 FROM project_skill_requirements psr_s
                    JOIN skills sk_s ON psr_s.skill_id = sk_s.id
                    WHERE psr_s.project_id = p.id AND sk_s.name LIKE ?
                )
            )
        """)
        where_params.extend([q_wildcard, q_wildcard, q_wildcard, q_wildcard, q_wildcard, q_wildcard])

    # 5. Required Skill Filter
    if skill_filter:
        where_clauses.append("""
            EXISTS (
                SELECT 1 FROM project_skill_requirements psr_k
                JOIN skills sk_k ON psr_k.skill_id = sk_k.id
                WHERE psr_k.project_id = p.id AND LOWER(sk_k.name) = LOWER(?)
            )
        """)
        where_params.append(skill_filter)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Count Query for Smart Pagination
    count_sql = f"""
        SELECT COUNT(p.id) as total
        FROM projects p
        WHERE {where_sql}
    """
    count_row = query_db(count_sql, where_params, one=True)
    total_count = count_row['total'] if count_row else 0
    total_pages = max(1, math.ceil(total_count / per_page))

    if page > total_pages and total_count > 0:
        page = total_pages
    offset = (page - 1) * per_page

    # Sorting options
    if sort_by == 'oldest':
        order_sql = "p.created_at ASC, p.id ASC"
    elif sort_by == 'popular':
        order_sql = "current_team_count DESC, p.created_at DESC, p.id DESC"
    elif sort_by == 'members_needed':
        order_sql = "(p.team_size_max - current_team_count) DESC, p.created_at DESC, p.id DESC"
    else:
        # Default: recently added
        sort_by = 'recent'
        order_sql = "p.created_at DESC, p.id DESC"

    # Main Query with clean 1:1 owner resolution (guarantees zero duplicate project cards)
    main_sql = f"""
        SELECT p.*,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   'Project Creator'
               ) as owner_name,
               COALESCE(
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   'CSE'
               ) as owner_branch,
               COALESCE(
                   (SELECT sp.year FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.year FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   '1st Year'
               ) as owner_year,
               COALESCE(
                   (SELECT sp.bio FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.bio FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_bio,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_email,
               (SELECT COUNT(DISTINCT uid) FROM (
                   SELECT p.owner_id as uid
                   UNION
                   SELECT user_id as uid FROM team_members WHERE project_id = p.id
               )) as current_team_count
        FROM projects p
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
    """
    query_params = list(where_params) + [per_page, offset]
    projects = query_db(main_sql, query_params)

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

        # Check if user has an application or is a member / owner
        p['user_application'] = None
        p['is_team_member'] = False
        p['is_owner'] = False
        if user_id:
            if is_project_owner(p, user_id):
                p['is_owner'] = True
                p['is_team_member'] = True
            else:
                mem = query_db("SELECT 1 FROM team_members WHERE project_id = ? AND user_id = ?", (p['id'], user_id), one=True)
                if mem:
                    p['is_team_member'] = True
                else:
                    app_record = query_db("SELECT * FROM project_applications WHERE project_id = ? AND applicant_id = ?", (p['id'], user_id), one=True)
                    p['user_application'] = app_record

    all_skills = query_db("SELECT name FROM skills WHERE active = 1 ORDER BY name")

    start_item = (page - 1) * per_page + 1 if total_count > 0 else 0
    end_item = min(page * per_page, total_count)
    has_prev = page > 1
    has_next = page < total_pages
    prev_page = page - 1
    next_page = page + 1
    pagination_pages = compute_pagination(page, total_pages)

    # Check for AJAX or JSON API requests
    is_json_req = (
        request.is_json
        or request.path.startswith('/api/')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    if is_json_req:
        return jsonify({
            'success': True,
            'projects': projects,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages,
                'start_item': start_item,
                'end_item': end_item,
                'has_prev': has_prev,
                'has_next': has_next,
                'prev_page': prev_page,
                'next_page': next_page,
                'pages': pagination_pages
            }
        })

    return render_template(
        'projects/list.html',
        projects=projects,
        all_skills=all_skills,
        categories=PROJECT_CATEGORIES,
        course_filter=course_filter,
        category_filter=category_filter,
        skill_filter=skill_filter,
        search_q=search_q,
        tab_filter=tab_filter,
        sort_by=sort_by,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        start_item=start_item,
        end_item=end_item,
        has_prev=has_prev,
        has_next=has_next,
        prev_page=prev_page,
        next_page=next_page,
        pagination_pages=pagination_pages
    )


def render_create_template(form_data=None):
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
        time_blocks=TIME_BLOCKS,
        form_data=form_data or {}
    )


@projects_bp.route('/projects/create', methods=['GET', 'POST'])
@projects_bp.route('/project/create', methods=['GET', 'POST'])
@projects_bp.route('/projects/new', methods=['GET', 'POST'])
@projects_bp.route('/project/new', methods=['GET', 'POST'])
@projects_bp.route('/api/projects', methods=['POST'])
@projects_bp.route('/api/projects/', methods=['POST'])
@projects_bp.route('/api/project', methods=['POST'])
@projects_bp.route('/api/projects/create', methods=['POST'])
@projects_bp.route('/api/project/create', methods=['POST'])
@projects_bp.route('/api/projects/publish', methods=['POST'])
@projects_bp.route('/api/project/publish', methods=['POST'])
@projects_bp.route('/projects/publish', methods=['POST'])
@projects_bp.route('/project/publish', methods=['POST'])
@login_required
def create_project():
    """Create a new course project with multi-step support, skills requirements, and draft/publish actions."""
    user_id = session['user_id']
    is_ajax = (
        request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    if request.method == 'POST':
        json_data = request.get_json(silent=True) or {}
        form_data = request.form

        def get_val(key, default=''):
            if form_data and key in form_data:
                return form_data.get(key, default)
            return json_data.get(key, default)

        title = str(
            get_val('title', '')
            or get_val('name', '')
            or get_val('projectName', '')
            or get_val('project_name', '')
        ).strip()
        description = str(
            get_val('description', '')
            or get_val('desc', '')
            or get_val('projectDescription', '')
            or get_val('project_description', '')
        ).strip()
        category = str(get_val('category', get_val('projectCategory', 'Web Development'))).strip()
        objectives = str(get_val('objectives', '')).strip()
        technologies = str(get_val('technologies', get_val('tech_stack', get_val('techStack', '')))).strip()
        duration = str(get_val('duration', '2–3 Months')).strip()
        collaboration_mode = str(get_val('collaboration_mode', get_val('mode', 'Hybrid'))).strip()
        availability = str(get_val('availability', 'Flexible')).strip()
        additional_requirements = str(get_val('additional_requirements', '')).strip()
        course_context = str(get_val('course_context', 'Innovation & Design Thinking (IDT)')).strip()

        # Team size parsing
        team_size_max_input = str(
            get_val('team_size_max', '')
            or get_val('team_size', '')
            or get_val('teamSize', '')
            or get_val('target_team_size', '')
            or get_val('targetTeamSize', '')
            or get_val('max_members', '4')
        ).strip()
        if team_size_max_input == 'custom':
            try:
                team_size_max = int(get_val('custom_team_size', 4))
            except (ValueError, TypeError):
                team_size_max = 4
        else:
            try:
                team_size_max = int(team_size_max_input)
            except (ValueError, TypeError):
                team_size_max = 4
        team_size_max = max(2, min(20, team_size_max))

        try:
            team_size_min = int(get_val('team_size_min', get_val('teamSizeMin', 2)))
        except (ValueError, TypeError):
            team_size_min = 2
        team_size_min = max(1, min(team_size_max, team_size_min))

        schedule_notes = str(get_val('schedule_notes', availability)).strip()
        action = str(get_val('action', get_val('submit_action', get_val('status', 'publish')))).strip().lower()
        if request.path.endswith('/publish'):
            action = 'publish'

        # Parse skills
        skills_data = parse_submitted_skills(form_data, json_data)

        # Validation for Publish
        if action == 'publish':
            if not title:
                err_msg = 'Project name is required to publish.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg}), 400
                flash(err_msg, 'danger')
                return render_create_template(form_data=request.form)

            if not description:
                err_msg = 'Project description is required to publish.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg}), 400
                flash(err_msg, 'danger')
                return render_create_template(form_data=request.form)

            if not skills_data:
                err_msg = 'Cannot publish project: You must declare at least one required skill before publishing.'
                if is_ajax:
                    return jsonify({'success': False, 'error': err_msg}), 400
                flash(err_msg, 'danger')
                return render_create_template(form_data=request.form)

            status = 'published'
        else:
            # Save as Draft
            if not title:
                title = 'Untitled Project (Draft)'
            status = 'draft'

        # Atomic transaction execution
        conn = get_db()
        try:
            cur = conn.cursor()

            # Insert into projects
            cur.execute("""
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
            proj_id = cur.lastrowid

            # Add creator as owner in team_members
            cur.execute("""
                INSERT OR IGNORE INTO team_members (project_id, user_id, role, joined_at)
                VALUES (?, ?, 'owner', CURRENT_TIMESTAMP)
            """, (proj_id, user_id))

            # Initialize project group chat
            group_name = f"{title} – Team Chat"
            cur.execute("""
                INSERT INTO conversations (conversation_type, project_id, conversation_name)
                VALUES ('project_group', ?, ?)
            """, (proj_id, group_name))
            conv_id = cur.lastrowid

            cur.execute("""
                INSERT OR IGNORE INTO conversation_participants (conversation_id, student_id, membership_status)
                VALUES (?, ?, 'active')
            """, (conv_id, user_id))

            # Save required skills
            seen_skills = set()
            for item in skills_data:
                s_name = str(item.get('name', '')).strip()
                if not s_name or s_name.lower() in seen_skills:
                    continue
                seen_skills.add(s_name.lower())

                priority_raw = str(item.get('priority', 'must-have')).strip().lower()
                if priority_raw in ['must have', 'must-have', 'must_have']:
                    priority = 'must-have'
                    weight = 3.0
                else:
                    priority = 'preferred'
                    weight = 1.0

                proficiency = str(item.get('proficiency', 'Intermediate')).strip().capitalize()
                if proficiency not in ['Beginner', 'Intermediate', 'Advanced', 'Expert']:
                    proficiency = 'Intermediate'

                # Catalog check or insertion
                cur.execute("SELECT id FROM skills WHERE LOWER(name) = LOWER(?)", (s_name,))
                skill_row = cur.fetchone()
                if skill_row:
                    skill_id = skill_row['id']
                else:
                    cur.execute("INSERT INTO skills (name, category, active) VALUES (?, ?, 1)", (s_name, category or 'Other'))
                    skill_id = cur.lastrowid

                cur.execute("""
                    INSERT OR REPLACE INTO project_skill_requirements (project_id, skill_id, priority, proficiency_level, weight)
                    VALUES (?, ?, ?, ?, ?)
                """, (proj_id, skill_id, priority, proficiency, weight))

            # Schedule availability slots
            selected_slots = []
            if json_data and 'slots' in json_data and isinstance(json_data['slots'], list):
                selected_slots = json_data['slots']
            elif hasattr(form_data, 'getlist'):
                selected_slots = form_data.getlist('slots')

            for slot_str in selected_slots:
                if '|' in slot_str:
                    day, block = slot_str.split('|', 1)
                    cur.execute("INSERT OR IGNORE INTO project_availability_slots (project_id, day_of_week, time_block) VALUES (?, ?, ?)", (proj_id, day, block))

            # Project interests
            selected_interests = []
            if json_data and 'interest_ids' in json_data and isinstance(json_data['interest_ids'], list):
                selected_interests = json_data['interest_ids']
            elif hasattr(form_data, 'getlist'):
                selected_interests = form_data.getlist('interest_ids')

            for iid in selected_interests:
                try:
                    cur.execute("INSERT OR IGNORE INTO project_interests (project_id, interest_id) VALUES (?, ?)", (proj_id, int(iid)))
                except Exception:
                    pass

            conn.commit()

        except Exception as e:
            conn.rollback()
            err_msg = f"Database operation failed: {str(e)}"
            if is_ajax:
                return jsonify({'success': False, 'error': err_msg}), 500
            flash(err_msg, 'danger')
            return render_create_template(form_data=request.form)
        finally:
            conn.close()

        # Audit logging (non-fatal)
        try:
            if status == 'published':
                log_event('project_published', actor_id=user_id, target_type='project', target_id=proj_id)
            else:
                log_event('project_created', actor_id=user_id, target_type='project', target_id=proj_id)
        except Exception:
            pass

        success_msg = (
            'Project published successfully! It is now visible in Active Projects seeking teammates.'
            if status == 'published' else
            'Project saved as draft! Only you can view and edit it until you publish.'
        )

        if is_ajax:
            return jsonify({
                'success': True,
                'message': success_msg,
                'project_id': proj_id,
                'redirect_url': url_for('projects.project_detail', project_id=proj_id),
                'status': status
            }), 201

        flash(success_msg, 'success' if status == 'published' else 'info')
        return redirect(url_for('projects.project_detail', project_id=proj_id))

    return render_create_template()


@projects_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@projects_bp.route('/projects/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    """Edit project information, team size, and skill requirements."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))
    if not is_project_owner(project, user_id):
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
@projects_bp.route('/projects/<project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    """Delete a project and its associated requirements and applications."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))
    if not is_project_owner(project, user_id):
        flash('Unauthorized: Only the project creator or an administrator can delete this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # Clean up dependent records in listings.db
    execute_db("DELETE FROM project_skill_requirements WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_availability_slots WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_interests WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM team_members WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM project_applications WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM invitations WHERE project_id = ?", (project_id,))
    execute_db("DELETE FROM projects WHERE id = ?", (project_id,))

    # If cloud sync enabled, delete from Supabase
    try:
        from app.supabase_client import is_cloud_enabled, delete_cloud_project
        if is_cloud_enabled():
            delete_cloud_project(project_id)
    except Exception:
        pass

    log_event('project_deleted', actor_id=user_id, target_type='project', target_id=project_id)
    flash('Project and all associated records deleted successfully.', 'info')
    if session.get('user_role') in ('admin', 'coordinator'):
        return redirect(request.referrer or url_for('admin.dashboard'))
    return redirect(url_for('projects.my_projects'))


@projects_bp.route('/projects/<int:project_id>')
@projects_bp.route('/projects/<project_id>')
def project_detail(project_id):
    """Detailed project view showing overview, team members, applications, and coverage."""
    user_id = session.get('user_id')
    project = query_db("""
        SELECT p.*,
               COALESCE(
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.display_name FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   'Project Creator'
               ) as owner_name,
               COALESCE(
                   (SELECT sp.bio FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.bio FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_bio,
               COALESCE(
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.branch FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   'CSE'
               ) as owner_branch,
               COALESCE(
                   (SELECT sp.year FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.year FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   '1st Year'
               ) as owner_year,
               COALESCE(
                   (SELECT sp.usn FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.usn FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_usn,
               COALESCE(
                   (SELECT sp.section FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.section FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_section,
               COALESCE(
                   (SELECT sp.institution FROM student_profiles sp WHERE sp.user_id = p.owner_id LIMIT 1),
                   (SELECT sp.institution FROM student_profiles sp WHERE sp.id = p.owner_id LIMIT 1),
                   'BMS Institute of Technology and Management'
               ) as owner_institution,
               COALESCE(
                   (SELECT u.email FROM users u WHERE u.id = p.owner_id LIMIT 1),
                   (SELECT u2.email FROM users u2 JOIN student_profiles sp2 ON u2.id = sp2.user_id WHERE sp2.id = p.owner_id LIMIT 1),
                   ''
               ) as owner_email
        FROM projects p
        WHERE p.id = ?
    """, (project_id,), one=True)

    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    is_owner = is_project_owner(project, user_id)

    # Team count and members
    current_team_count = get_project_team_count(project_id, project['owner_id'])
    available_positions = max(0, project['team_size_max'] - current_team_count)

    # Accepted team members
    team_members_list = query_db("""
        SELECT tm.*, sp.display_name, sp.branch, sp.year, sp.section, sp.bio, u.email
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        LEFT JOIN student_profiles sp ON u.id = sp.user_id
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
                LEFT JOIN student_profiles sp ON u.id = sp.user_id
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
            LEFT JOIN student_profiles sp ON u.id = sp.user_id
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

    if is_project_owner(project, user_id):
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
    if not project or not is_project_owner(project, user_id):
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
    if not project or not is_project_owner(project, user_id):
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if is_project_owner(project, member_id, allow_admin=False):
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
        WHERE (
            p.owner_id = ?
            OR p.owner_id = (SELECT id FROM student_profiles WHERE user_id = ?)
            OR p.owner_id IN (SELECT user_id FROM student_profiles WHERE id = ?)
            OR EXISTS (
                SELECT 1 FROM team_members tm
                WHERE tm.project_id = p.id
                  AND LOWER(tm.role) = 'owner'
                  AND (tm.user_id = ? OR tm.user_id = (SELECT id FROM student_profiles WHERE user_id = ?))
            )
        )
        ORDER BY p.updated_at DESC
    """, (user_id, user_id, user_id, user_id, user_id))

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
               COALESCE(sp.display_name, u.email, 'Student') as owner_name,
               COALESCE(sp.branch, 'CSE') as owner_branch
        FROM project_applications pa
        JOIN projects p ON pa.project_id = p.id
        LEFT JOIN users u ON (p.owner_id = u.id OR p.owner_id = (SELECT sp2.id FROM student_profiles sp2 WHERE sp2.user_id = u.id))
        LEFT JOIN student_profiles sp ON (sp.user_id = u.id OR sp.id = p.owner_id)
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
@projects_bp.route('/projects/<project_id>/requirements', methods=['POST'])
@login_required
def update_requirements(project_id):
    """Add or remove skill requirement for project (FR-06)."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or not is_project_owner(project, user_id):
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


@projects_bp.route('/projects/<project_id>/publish', methods=['POST'])
@projects_bp.route('/api/projects/<project_id>/publish', methods=['POST'])
@projects_bp.route('/project/<project_id>/publish', methods=['POST'])
@projects_bp.route('/api/project/<project_id>/publish', methods=['POST'])
@login_required
def publish_project(project_id):
    """Publish a draft project or create & publish atomically if project_id is unassigned or payload is provided."""
    user_id = session['user_id']
    is_ajax = (
        request.is_json
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )

    # 1. Parse project_id as integer if possible
    pid_int = None
    try:
        pid_int = int(project_id)
    except (ValueError, TypeError):
        pid_int = None

    project = None
    if pid_int is not None and pid_int > 0:
        project = query_db("SELECT * FROM projects WHERE id = ?", (pid_int,), one=True)

    # 2. If project does not exist (e.g. project_id is 'undefined', 'null', 'new', 0, or not found):
    if not project:
        # Check if project creation payload was submitted with this request
        json_data = request.get_json(silent=True) or {}
        form_data = request.form
        has_title = bool(
            form_data.get('title') or form_data.get('name') or
            json_data.get('title') or json_data.get('name') or
            form_data.get('project_name') or json_data.get('project_name')
        )
        has_desc = bool(
            form_data.get('description') or form_data.get('desc') or
            json_data.get('description') or json_data.get('desc')
        )
        has_skills = bool(
            form_data.get('skills_json') or json_data.get('skills_json') or
            form_data.get('skills') or json_data.get('skills') or
            form_data.get('required_skills') or json_data.get('required_skills')
        )

        if has_title or has_desc or has_skills:
            # Delegate directly to create_project() to create and publish atomically
            return create_project()

        # Truly not found and no creation data
        if is_ajax:
            return jsonify({'success': False, 'error': f'Project resource "{project_id}" not found.'}), 404
        flash('Project not found.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # 3. Ownership check for existing project
    if not is_project_owner(project, user_id):
        if is_ajax:
            return jsonify({'success': False, 'error': 'Unauthorized action: You do not own this project.'}), 403
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    # 4. If new skills were submitted with the publish request, save them
    json_data = request.get_json(silent=True) or {}
    form_data = request.form
    new_skills = parse_submitted_skills(form_data, json_data)
    if new_skills:
        conn = get_db()
        cur = conn.cursor()
        for item in new_skills:
            s_name = str(item.get('name', '')).strip()
            if not s_name:
                continue
            prio_raw = str(item.get('priority', 'must-have')).strip().lower()
            prio = 'must-have' if prio_raw in ['must have', 'must-have', 'must_have'] else 'preferred'
            weight = 3.0 if prio == 'must-have' else 1.0
            prof = str(item.get('proficiency', 'Intermediate')).strip().capitalize()
            if prof not in ['Beginner', 'Intermediate', 'Advanced', 'Expert']:
                prof = 'Intermediate'

            cur.execute("SELECT id FROM skills WHERE LOWER(name) = LOWER(?)", (s_name,))
            s_row = cur.fetchone()
            if s_row:
                s_id = s_row['id']
            else:
                cur.execute("INSERT INTO skills (name, category, active) VALUES (?, 'Other', 1)", (s_name,))
                s_id = cur.lastrowid

            cur.execute("""
                INSERT OR REPLACE INTO project_skill_requirements (project_id, skill_id, priority, proficiency_level, weight)
                VALUES (?, ?, ?, ?, ?)
            """, (pid_int, s_id, prio, prof, weight))
        conn.commit()
        conn.close()

    # 5. Validate that at least 1 required skill exists
    req_cnt_row = query_db("SELECT COUNT(*) as cnt FROM project_skill_requirements WHERE project_id = ?", (pid_int,), one=True)
    req_cnt = req_cnt_row['cnt'] if req_cnt_row else 0
    if req_cnt == 0:
        if is_ajax:
            return jsonify({'success': False, 'error': 'Cannot publish project: You must declare at least one required skill first.'}), 400
        flash('Cannot publish project: You must declare at least one required skill first.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=pid_int))

    # 6. Update status to published
    execute_db("UPDATE projects SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (pid_int,))
    log_event('project_published', actor_id=user_id, target_type='project', target_id=pid_int)

    if is_ajax:
        return jsonify({
            'success': True,
            'message': 'Project published! Classmates can now discover it and apply.',
            'project_id': pid_int,
            'redirect_url': url_for('projects.project_detail', project_id=pid_int),
            'status': 'published'
        }), 200

    flash('Project published! Classmates can now discover it and apply.', 'success')
    return redirect(url_for('projects.project_detail', project_id=pid_int))


@projects_bp.route('/projects/<int:project_id>/close', methods=['POST'])
@projects_bp.route('/projects/<project_id>/close', methods=['POST'])
@login_required
def close_project(project_id):
    """Toggle project status between closed and published."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or not is_project_owner(project, user_id):
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if project['status'] == 'closed':
        execute_db("UPDATE projects SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project['id'],))
        flash('Project reopened! Now accepting teammate applications.', 'success')
    else:
        execute_db("UPDATE projects SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project['id'],))
        log_event('project_closed', actor_id=user_id, target_type='project', target_id=project['id'])
        flash('Project closed. Team is now finalized and no longer accepting applications.', 'info')

    return redirect(url_for('projects.project_detail', project_id=project['id']))


@projects_bp.route('/projects/<int:project_id>/matches')
@projects_bp.route('/projects/<project_id>/matches')
@login_required
def match_candidates(project_id):
    """Ranks candidates using explainable formula: Match Score = 0.65 * Skill + 0.25 * Availability + 0.10 * Interest"""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or not is_project_owner(project, user_id):
        flash('Only the project owner can view match recommendations for this project.', 'danger')
        return redirect(url_for('projects.project_detail', project_id=project['id']) if project else url_for('projects.list_projects'))

    filters = {
        'skill_id': request.args.get('skill_id'),
        'branch': request.args.get('branch'),
        'year': request.args.get('year'),
        'section': request.args.get('section'),
        'min_score': request.args.get('min_score'),
        'fills_gap_only': request.args.get('fills_gap_only') == '1'
    }

    candidates = calculate_matches_for_project(project['id'], filters=filters)
    coverage = compute_team_skill_coverage(project['id'])
    all_skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")

    log_event('match_list_viewed', actor_id=user_id, target_type='project', target_id=project['id'], metadata={'results_count': len(candidates)})

    return render_template(
        'projects/matches.html',
        project=project,
        candidates=candidates,
        coverage=coverage,
        filters=filters,
        all_skills=all_skills
    )


@projects_bp.route('/api/projects/<int:project_id>/matches')
@projects_bp.route('/api/projects/<project_id>/matches')
@login_required
def api_matches(project_id):
    """JSON API endpoint for matches."""
    user_id = session['user_id']
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project or not is_project_owner(project, user_id):
        return jsonify({'error': 'Unauthorized: Only the project owner can view match recommendations for this project.'}), 403

    filters = {
        'skill_id': request.args.get('skill_id'),
        'branch': request.args.get('branch'),
        'year': request.args.get('year'),
        'section': request.args.get('section'),
        'min_score': request.args.get('min_score'),
        'fills_gap_only': request.args.get('fills_gap_only') == '1'
    }

    candidates = calculate_matches_for_project(project['id'], filters=filters)
    return jsonify({'project_id': project['id'], 'matches': candidates})


@projects_bp.route('/api/projects/<int:project_id>/team')
def api_team(project_id):
    """JSON API endpoint for team skill coverage."""
    cov = compute_team_skill_coverage(project_id)
    if not cov:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(cov)
