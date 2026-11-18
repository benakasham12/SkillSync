"""
Analytics and Audit Logging module based on PRD Section 9.
Logs core user events and computes North Star & operational metrics.
"""

import json
from datetime import datetime
from app.models import execute_db, query_db


def log_event(event_name, actor_id=None, target_type=None, target_id=None, metadata=None, db_path=None):
    """Logs an audit and product analytics event."""
    meta_str = json.dumps(metadata) if metadata else None
    execute_db("""
        INSERT INTO audit_events (event_name, actor_id, target_type, target_id, metadata_json)
        VALUES (?, ?, ?, ?, ?)
    """, (event_name, actor_id, target_type, target_id, meta_str), db_path=db_path)


def get_analytics_summary(db_path=None):
    """
    Computes key performance metrics specified in PRD Section 9:
    - Profile completion rate
    - Project publish rate
    - Must-have skill coverage rate
    - Match-to-invitation rate
    - Invitation acceptance rate
    - North Star Metric: % of projects reaching target team size with 100% must-have skill coverage
    """
    # 1. Total registered accounts
    total_users_row = query_db("SELECT COUNT(*) as cnt FROM users WHERE role = 'student'", one=True, db_path=db_path)
    total_users = total_users_row['cnt'] if total_users_row else 0

    # Match ready profiles
    match_ready_row = query_db("SELECT COUNT(*) as cnt FROM student_profiles WHERE is_match_ready = 1", one=True, db_path=db_path)
    match_ready_profiles = match_ready_row['cnt'] if match_ready_row else 0

    profile_completion_rate = round((match_ready_profiles / total_users * 100.0), 1) if total_users > 0 else 0.0

    # 2. Projects created vs published
    total_projects_row = query_db("SELECT COUNT(*) as cnt FROM projects", one=True, db_path=db_path)
    total_projects = total_projects_row['cnt'] if total_projects_row else 0

    published_projects_row = query_db("SELECT COUNT(*) as cnt FROM projects WHERE status IN ('published', 'closed')", one=True, db_path=db_path)
    published_projects = published_projects_row['cnt'] if published_projects_row else 0

    project_publish_rate = round((published_projects / total_projects * 100.0), 1) if total_projects > 0 else 0.0

    # 3. Invitations: sent, accepted, declined
    invitations_stats = query_db("""
        SELECT 
            COUNT(*) as total_invitations,
            SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted,
            SUM(CASE WHEN status = 'declined' THEN 1 ELSE 0 END) as declined,
            SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
        FROM invitations
    """, one=True, db_path=db_path)

    total_invites = invitations_stats['total_invitations'] or 0
    accepted_invites = invitations_stats['accepted'] or 0
    declined_invites = invitations_stats['declined'] or 0
    responded_invites = accepted_invites + declined_invites

    invitation_acceptance_rate = round((accepted_invites / responded_invites * 100.0), 1) if responded_invites > 0 else 0.0

    # 4. North Star Metric & Must-have Skill Coverage
    # Fetch all published/closed projects
    active_projects = query_db("SELECT id, team_size_min, team_size_max FROM projects WHERE status IN ('published', 'closed')", db_path=db_path)
    
    successful_projects = 0
    total_must_have_skills_all = 0
    total_must_have_skills_covered_all = 0

    from app.matching import compute_team_skill_coverage

    for p in active_projects:
        cov = compute_team_skill_coverage(p['id'], db_path=db_path)
        if cov:
            total_must_have_skills_all += cov['must_have_count']
            total_must_have_skills_covered_all += cov['must_have_covered']
            # Reached target size (at least team_size_min) and covered all must-haves
            if cov['current_team_size'] >= cov['team_size_min'] and cov['all_must_haves_covered']:
                successful_projects += 1

    overall_must_have_coverage_rate = round(
        (total_must_have_skills_covered_all / total_must_have_skills_all * 100.0), 1
    ) if total_must_have_skills_all > 0 else 0.0

    north_star_metric = round(
        (successful_projects / len(active_projects) * 100.0), 1
    ) if active_projects else 0.0

    # Recent activity events
    recent_events = query_db("""
        SELECT ae.*, u.email as actor_email
        FROM audit_events ae
        LEFT JOIN users u ON ae.actor_id = u.id
        ORDER BY ae.created_at DESC
        LIMIT 20
    """, db_path=db_path)

    return {
        'total_users': total_users,
        'match_ready_profiles': match_ready_profiles,
        'profile_completion_rate': profile_completion_rate,
        'total_projects': total_projects,
        'published_projects': published_projects,
        'project_publish_rate': project_publish_rate,
        'total_invitations': total_invites,
        'accepted_invites': accepted_invites,
        'declined_invites': declined_invites,
        'invitation_acceptance_rate': invitation_acceptance_rate,
        'overall_must_have_coverage_rate': overall_must_have_coverage_rate,
        'north_star_metric': north_star_metric,
        'successful_projects': successful_projects,
        'evaluated_projects_count': len(active_projects),
        'recent_events': recent_events
    }
