"""
Matching engine implementing PRD Section 6 requirements:
- Explainable, requirement-first candidate ranking
- Formula: Match Score = 0.65 * Skill Fit + 0.25 * Availability Fit + 0.10 * Interest Fit
- Detailed breakdown of matched skills, missing must-haves, missing preferreds, availability overlap, shared interests
- Team gap awareness: highlights candidates who cover skills missing from the current roster
"""

from app.models import query_db, get_db


def calculate_matches_for_project(project_id, filters=None, db_path=None):
    """
    Computes ranked candidate recommendations for a given project.
    Filters can include:
      - skill_id (optional filter)
      - branch, year, section
      - min_score (optional threshold)
      - interest_id
    """
    # 1. Fetch project details
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True, db_path=db_path)
    if not project:
        return []

    # 2. Fetch project skill requirements
    requirements = query_db("""
        SELECT psr.*, s.name as skill_name, s.category as skill_category
        FROM project_skill_requirements psr
        JOIN skills s ON psr.skill_id = s.id
        WHERE psr.project_id = ?
    """, (project_id,), db_path=db_path)

    total_weight = sum(r['weight'] for r in requirements) if requirements else 0.0

    # 3. Fetch project availability slots
    proj_slots = query_db("""
        SELECT day_of_week, time_block
        FROM project_availability_slots
        WHERE project_id = ?
    """, (project_id,), db_path=db_path)
    proj_slot_set = {(s['day_of_week'], s['time_block']) for s in proj_slots}

    # 4. Fetch project interests
    proj_interests = query_db("""
        SELECT pi.interest_id, i.name as interest_name
        FROM project_interests pi
        JOIN interests i ON pi.interest_id = i.id
        WHERE pi.project_id = ?
    """, (project_id,), db_path=db_path)
    proj_interest_ids = {pi['interest_id'] for pi in proj_interests}
    proj_interest_names = {pi['interest_name'] for pi in proj_interests}

    # 5. Fetch current team member user IDs
    existing_members = query_db("""
        SELECT user_id FROM team_members WHERE project_id = ?
    """, (project_id,), db_path=db_path)
    existing_member_ids = {m['user_id'] for m in existing_members}
    existing_member_ids.add(project['owner_id'])

    # 6. Fetch existing skills covered by current team
    team_skills_query = query_db("""
        SELECT DISTINCT ss.skill_id
        FROM student_skills ss
        JOIN team_members tm ON ss.user_id = tm.user_id
        WHERE tm.project_id = ?
        UNION
        SELECT DISTINCT ss.skill_id
        FROM student_skills ss
        WHERE ss.user_id = ?
    """, (project_id, project['owner_id']), db_path=db_path)
    team_covered_skill_ids = {ts['skill_id'] for ts in team_skills_query}

    # 7. Fetch active, match-ready candidate profiles excluding existing team members
    candidates_raw = query_db("""
        SELECT u.id as user_id, u.email, sp.display_name, sp.usn, sp.branch, sp.year, sp.section,
               sp.institution, sp.bio, sp.github_url, sp.linkedin_url, sp.portfolio_url,
               sp.visibility, sp.show_contact_after_accept, sp.is_match_ready
        FROM users u
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE u.status = 'active'
          AND sp.is_match_ready = 1
          AND sp.visibility != 'private'
          AND u.id NOT IN ({seq})
    """.format(seq=','.join(['?'] * len(existing_member_ids))), list(existing_member_ids), db_path=db_path)

    # 8. Check pending invitations to annotate candidates
    invitations = query_db("""
        SELECT id, invitee_id, status
        FROM invitations
        WHERE project_id = ? AND status = 'pending'
    """, (project_id,), db_path=db_path)
    pending_invite_map = {inv['invitee_id']: inv['id'] for inv in invitations}

    candidates = []

    for c in candidates_raw:
        uid = c['user_id']

        # Apply cohort filtering if visibility is 'cohort_only'
        # In BMSIT&M cohort, compare branch/institution
        if c['visibility'] == 'cohort_only':
            owner_profile = query_db("SELECT * FROM student_profiles WHERE user_id = ?", (project['owner_id'],), one=True, db_path=db_path)
            if owner_profile and owner_profile.get('institution') and c.get('institution'):
                if owner_profile['institution'].lower() != c['institution'].lower():
                    continue

        # Fetch candidate's skills
        candidate_skills = query_db("""
            SELECT ss.skill_id, ss.proficiency, ss.self_reported, s.name as skill_name, s.category as skill_category
            FROM student_skills ss
            JOIN skills s ON ss.skill_id = s.id
            WHERE ss.user_id = ?
        """, (uid,), db_path=db_path)
        cand_skill_map = {cs['skill_id']: cs for cs in candidate_skills}

        # Fetch candidate's availability
        cand_slots = query_db("""
            SELECT day_of_week, time_block
            FROM availability_slots
            WHERE user_id = ?
        """, (uid,), db_path=db_path)
        cand_slot_set = {(s['day_of_week'], s['time_block']) for s in cand_slots}

        # Fetch candidate's interests
        cand_interests = query_db("""
            SELECT si.interest_id, i.name as interest_name
            FROM student_interests si
            JOIN interests i ON si.interest_id = i.id
            WHERE si.user_id = ?
        """, (uid,), db_path=db_path)
        cand_interest_ids = {ci['interest_id'] for ci in cand_interests}

        # --- A. Skill Fit Calculation ---
        matched_skills = []
        missing_must_haves = []
        missing_preferred = []
        covered_weight = 0.0
        fills_unmet_team_gap = False

        for req in requirements:
            req_skill_id = req['skill_id']
            if req_skill_id in cand_skill_map:
                student_skill = cand_skill_map[req_skill_id]
                matched_skills.append({
                    'skill_id': req_skill_id,
                    'name': req['skill_name'],
                    'category': req['skill_category'],
                    'proficiency': student_skill['proficiency'],
                    'self_reported': bool(student_skill['self_reported']),
                    'priority': req['priority'],
                    'weight': req['weight']
                })
                covered_weight += req['weight']
                # Check if this matches a skill the team doesn't have yet
                if req_skill_id not in team_covered_skill_ids:
                    fills_unmet_team_gap = True
            else:
                if req['priority'] == 'must-have':
                    missing_must_haves.append(req['skill_name'])
                else:
                    missing_preferred.append(req['skill_name'])

        if total_weight > 0:
            skill_fit = round((covered_weight / total_weight) * 100.0, 1)
        else:
            skill_fit = 0.0

        # --- B. Availability Fit Calculation ---
        overlap_slots = list(proj_slot_set.intersection(cand_slot_set))
        has_availability_data = len(proj_slot_set) > 0 and len(cand_slot_set) > 0
        if len(proj_slot_set) > 0:
            avail_fit = round((len(overlap_slots) / len(proj_slot_set)) * 100.0, 1)
        else:
            # PRD Section 6.1: "If project schedule is not known, show 'not enough availability data' rather than treating it as 100%"
            avail_fit = 0.0

        # --- C. Interest Fit Calculation ---
        shared_tag_ids = proj_interest_ids.intersection(cand_interest_ids)
        shared_interests = [ci['interest_name'] for ci in cand_interests if ci['interest_id'] in shared_tag_ids]
        has_interest_data = len(proj_interest_ids) > 0
        if len(proj_interest_ids) > 0:
            interest_fit = round((len(shared_tag_ids) / len(proj_interest_ids)) * 100.0, 1)
        else:
            interest_fit = 0.0

        # --- D. Total Match Score (PRD formula: 0.65*Skill + 0.25*Avail + 0.10*Interest) ---
        match_score = round(
            (0.65 * skill_fit) +
            (0.25 * avail_fit) +
            (0.10 * interest_fit),
            1
        )

        candidate_record = {
            'user_id': uid,
            'display_name': c['display_name'],
            'usn': c['usn'],
            'branch': c['branch'],
            'year': c['year'],
            'section': c['section'],
            'institution': c['institution'],
            'bio': c['bio'],
            'github_url': c['github_url'],
            'linkedin_url': c['linkedin_url'],
            'portfolio_url': c['portfolio_url'],
            'email': c['email'] if not c['show_contact_after_accept'] else None, # Hidden until accepted
            'skill_fit': skill_fit,
            'availability_fit': avail_fit,
            'has_availability_data': has_availability_data,
            'interest_fit': interest_fit,
            'has_interest_data': has_interest_data,
            'match_score': match_score,
            'matched_skills': matched_skills,
            'missing_must_haves': missing_must_haves,
            'missing_preferred': missing_preferred,
            'overlap_slots': [{'day': s[0], 'time': s[1]} for s in overlap_slots],
            'overlap_count': len(overlap_slots),
            'shared_interests': shared_interests,
            'fills_unmet_team_gap': fills_unmet_team_gap,
            'pending_invitation_id': pending_invite_map.get(uid),
            'all_skills': candidate_skills
        }

        # Apply runtime filters
        if filters:
            if filters.get('skill_id'):
                skill_id_filter = int(filters['skill_id'])
                if skill_id_filter not in cand_skill_map:
                    continue
            if filters.get('branch') and c['branch'].lower() != filters['branch'].lower():
                continue
            if filters.get('year') and c['year'].lower() != filters['year'].lower():
                continue
            if filters.get('section') and c['section'].lower() != filters['section'].lower():
                continue
            if filters.get('min_score') and match_score < float(filters['min_score']):
                continue
            if filters.get('fills_gap_only') and not fills_unmet_team_gap:
                continue

        candidates.append(candidate_record)

    # Sort descending by match_score, then skill_fit, then availability overlap
    candidates.sort(key=lambda x: (x['match_score'], x['skill_fit'], x['overlap_count']), reverse=True)
    return candidates


def compute_team_skill_coverage(project_id, db_path=None):
    """
    Computes team skill coverage for a project:
    - Lists all required skills (must-have and preferred)
    - Checks which members cover each skill
    - Computes coverage percentages
    """
    project = query_db("SELECT * FROM projects WHERE id = ?", (project_id,), one=True, db_path=db_path)
    if not project:
        return None

    # Required skills
    requirements = query_db("""
        SELECT psr.*, s.name as skill_name, s.category as skill_category
        FROM project_skill_requirements psr
        JOIN skills s ON psr.skill_id = s.id
        WHERE psr.project_id = ?
        ORDER BY psr.priority DESC, psr.weight DESC
    """, (project_id,), db_path=db_path)

    # All accepted members (including owner)
    members = query_db("""
        SELECT u.id as user_id, u.email, sp.display_name, sp.usn, tm.role, tm.joined_at
        FROM team_members tm
        JOIN users u ON tm.user_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE tm.project_id = ?
        UNION
        SELECT u.id as user_id, u.email, sp.display_name, sp.usn, 'owner' as role, p.created_at as joined_at
        FROM projects p
        JOIN users u ON p.owner_id = u.id
        JOIN student_profiles sp ON u.id = sp.user_id
        WHERE p.id = ?
        ORDER BY role DESC, display_name ASC
    """, (project_id, project_id), db_path=db_path)

    # Get skills for each member
    member_skills = {}
    for m in members:
        skills = query_db("""
            SELECT s.id as skill_id, s.name as skill_name, ss.proficiency, ss.self_reported
            FROM student_skills ss
            JOIN skills s ON ss.skill_id = s.id
            WHERE ss.user_id = ?
        """, (m['user_id'],), db_path=db_path)
        member_skills[m['user_id']] = {s['skill_id']: s for s in skills}

    skill_coverage = []
    must_have_count = 0
    must_have_covered = 0
    total_count = len(requirements)
    total_covered = 0

    for req in requirements:
        is_must = req['priority'] in ['must-have', 'must_have', 'Must Have']
        if is_must:
            must_have_count += 1

        covered_by = []
        for m in members:
            uid = m['user_id']
            if uid in member_skills and req['skill_id'] in member_skills[uid]:
                sk_info = member_skills[uid][req['skill_id']]
                covered_by.append({
                    'user_id': uid,
                    'display_name': m['display_name'],
                    'proficiency': sk_info['proficiency'],
                    'self_reported': bool(sk_info['self_reported'])
                })

        covered = len(covered_by) > 0
        if covered:
            total_covered += 1
            if is_must:
                must_have_covered += 1

        skill_coverage.append({
            'skill_id': req['skill_id'],
            'skill_name': req['skill_name'],
            'category': req['skill_category'],
            'priority': 'must-have' if is_must else 'nice-to-have',
            'proficiency_level': req.get('proficiency_level', 'intermediate'),
            'weight': req['weight'],
            'is_covered': covered,
            'covered_by': covered_by
        })

    must_have_pct = round((must_have_covered / must_have_count * 100.0), 1) if must_have_count > 0 else 100.0
    overall_pct = round((total_covered / total_count * 100.0), 1) if total_count > 0 else 100.0

    return {
        'project_id': project_id,
        'title': project['title'],
        'team_size_min': project['team_size_min'],
        'team_size_max': project['team_size_max'],
        'current_team_size': len(members),
        'members': members,
        'requirements': skill_coverage,
        'must_have_count': must_have_count,
        'must_have_covered': must_have_covered,
        'must_have_coverage_pct': must_have_pct,
        'total_requirements': total_count,
        'total_covered': total_covered,
        'overall_coverage_pct': overall_pct,
        'all_must_haves_covered': must_have_covered == must_have_count,
        'is_team_full': len(members) >= project['team_size_max']
    }
