"""
Supabase Cloud Database Client for SkillSync.

Enables secure integration with Supabase REST API (PostgREST)
to publish and synchronize public project listings and catalogs in the cloud
so that everyone can discover and view projects globally.

Zero external dependencies: uses standard library urllib.request and json.
Credentials are read strictly from environment variables / .env file.
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from app.env_loader import load_dotenv

# Ensure .env is loaded
load_dotenv()


def get_supabase_config():
    """Retrieve Supabase credentials and enablement status from environment."""
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '').strip()
    anon_key = os.environ.get('SUPABASE_KEY', '').strip()
    # Server-side operations prefer the service_role key to satisfy RLS policies
    key = service_key or anon_key
    rest_url = os.environ.get('SUPABASE_REST_URL', '').rstrip('/')
    if url and not rest_url:
        rest_url = f"{url}/rest/v1"

    use_cloud = os.environ.get('USE_SUPABASE', 'false').lower() in ('true', '1', 'yes')

    return {
        'url': url,
        'key': key,
        'anon_key': anon_key,
        'service_role_key': service_key,
        'rest_url': rest_url,
        'enabled': use_cloud and bool(url) and bool(key)
    }


def is_cloud_enabled():
    """Return True if cloud sync is enabled and credentials are present."""
    config = get_supabase_config()
    return config['enabled']


def supabase_request(endpoint, method='GET', data=None, query_params=None, extra_headers=None, timeout=10):
    """
    Execute an authenticated HTTP request to the Supabase PostgREST API.

    :param endpoint: Table or RPC path (e.g. 'projects', 'skills')
    :param method: HTTP method ('GET', 'POST', 'PATCH', 'DELETE')
    :param data: Python dict or list to send as JSON payload
    :param query_params: Dict of PostgREST query parameters (e.g. {'status': 'eq.published'})
    :param extra_headers: Additional headers to merge
    :param timeout: Request timeout in seconds
    :return: (status_code, parsed_json_or_text)
    """
    config = get_supabase_config()
    if not config['key'] or not config['rest_url']:
        raise ValueError("Supabase is not configured. Missing SUPABASE_URL or SUPABASE_KEY.")

    clean_endpoint = endpoint.lstrip('/')
    full_url = f"{config['rest_url']}/{clean_endpoint}"

    if query_params:
        encoded_params = urllib.parse.urlencode(query_params)
        full_url = f"{full_url}?{encoded_params}"

    headers = {
        'apikey': config['key'],
        'Authorization': f"Bearer {config['key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    if method in ('POST', 'PATCH', 'PUT'):
        # Request representation of modified data
        headers['Prefer'] = 'return=representation'

    if extra_headers:
        headers.update(extra_headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode('utf-8')

    req = urllib.request.Request(full_url, data=body_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            content = response.read().decode('utf-8')
            try:
                parsed = json.loads(content) if content else None
            except json.JSONDecodeError:
                parsed = content
            return status, parsed
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8')
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = err_body
        return e.code, err_json
    except Exception as e:
        return 0, {'error': str(e)}


def ping_supabase():
    """
    Check connectivity and authentication against the Supabase instance.
    Returns (is_connected: bool, message: str)
    """
    config = get_supabase_config()
    if not config['url'] or not config['key']:
        return False, "Supabase credentials missing. Check .env file."

    # Try querying the skills table
    status, res = supabase_request('skills', method='GET', query_params={'limit': 1}, timeout=5)

    if status in (200, 206):
        return True, "Successfully connected to Supabase cloud database!"
    elif status == 404 and isinstance(res, dict) and 'Could not find the table' in str(res.get('message', '')):
        return True, "Connected to Supabase! (Tables need to be created via supabase_schema.sql)"
    elif status == 401:
        return False, f"Supabase Authentication Error (401): {res}"
    else:
        return False, f"Supabase Connection Response ({status}): {res}"


def fetch_cloud_projects(status='published', limit=50):
    """Retrieve published project listings from Supabase."""
    params = {'select': '*', 'limit': limit}
    if status:
        params['status'] = f"eq.{status}"

    code, data = supabase_request('projects', method='GET', query_params=params)
    if code == 200 and isinstance(data, list):
        return data
    return []


def upsert_cloud_project(project_dict):
    """
    Upsert a single project listing into Supabase cloud database.
    """
    headers = {'Prefer': 'resolution=merge-duplicates,return=representation'}
    code, data = supabase_request('projects', method='POST', data=project_dict, extra_headers=headers)
    return code in (200, 201), data


def delete_cloud_project(project_id):
    """
    Permanently delete a project listing and all its associated child records from Supabase cloud database.
    Cascade-deletes from dependent tables first:
    - project_skill_requirements
    - project_availability_slots
    - project_interests
    - team_members
    - project_applications
    - invitations
    - projects
    """
    if not is_cloud_enabled():
        return False, "Cloud sync is disabled."

    p_param = {'project_id': f"eq.{project_id}"}
    extra_headers = {'Prefer': 'return=representation'}

    # 1. Clean up dependent child records
    for child_table in [
        'project_skill_requirements',
        'project_availability_slots',
        'project_interests',
        'team_members',
        'project_applications',
        'invitations'
    ]:
        try:
            supabase_request(child_table, method='DELETE', query_params=p_param, extra_headers=extra_headers)
        except Exception:
            pass

    # 2. Delete parent project record
    params = {'id': f"eq.{project_id}"}
    code, data = supabase_request('projects', method='DELETE', query_params=params, extra_headers=extra_headers)
    success = code in (200, 204)
    return success, data


def sync_local_listings_to_cloud(db_path=None):
    """
    Synchronize all public listings, skills, requirements, and catalogs
    from the local listings.db to Supabase cloud database.
    """
    import sqlite3
    from app.models import get_listings_db

    if not is_cloud_enabled():
        return {'success': False, 'message': 'Cloud database integration is disabled in .env (USE_SUPABASE=false).'}

    conn = get_listings_db(db_path)
    report = {
        'skills': 0, 'interests': 0, 'projects': 0, 'requirements': 0,
        'availability_slots': 0, 'project_interests': 0, 'team_members': 0,
        'applications': 0, 'invitations': 0, 'errors': []
    }

    try:
        # 1. Sync Skills Catalog
        skills = [dict(r) for r in conn.execute("SELECT id, name, category, active FROM skills").fetchall()]
        if skills:
            code, res = supabase_request('skills', method='POST', data=skills,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['skills'] = len(skills)
            else:
                report['errors'].append(f"Skills sync error ({code}): {res}")

        # 2. Sync Interests Catalog
        interests = [dict(r) for r in conn.execute("SELECT id, name, category FROM interests").fetchall()]
        if interests:
            code, res = supabase_request('interests', method='POST', data=interests,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['interests'] = len(interests)
            else:
                report['errors'].append(f"Interests sync error ({code}): {res}")

        # 3. Sync Projects
        projects = [dict(r) for r in conn.execute("SELECT * FROM projects").fetchall()]
        if projects:
            code, res = supabase_request('projects', method='POST', data=projects,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['projects'] = len(projects)
            else:
                report['errors'].append(f"Projects sync error ({code}): {res}")

        # 4. Sync Skill Requirements
        reqs = [dict(r) for r in conn.execute("SELECT * FROM project_skill_requirements").fetchall()]
        if reqs:
            code, res = supabase_request('project_skill_requirements', method='POST', data=reqs,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['requirements'] = len(reqs)
            else:
                report['errors'].append(f"Project skill requirements sync error ({code}): {res}")

        # 5. Sync Project Availability Slots
        slots = [dict(r) for r in conn.execute("SELECT * FROM project_availability_slots").fetchall()]
        if slots:
            code, res = supabase_request('project_availability_slots', method='POST', data=slots,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['availability_slots'] = len(slots)
            else:
                report['errors'].append(f"Availability slots sync error ({code}): {res}")

        # 6. Sync Project Interests
        p_interests = [dict(r) for r in conn.execute("SELECT * FROM project_interests").fetchall()]
        if p_interests:
            code, res = supabase_request('project_interests', method='POST', data=p_interests,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['project_interests'] = len(p_interests)
            else:
                report['errors'].append(f"Project interests sync error ({code}): {res}")

        # 7. Sync Team Members
        members = [dict(r) for r in conn.execute("SELECT * FROM team_members").fetchall()]
        if members:
            code, res = supabase_request('team_members', method='POST', data=members,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['team_members'] = len(members)
            else:
                report['errors'].append(f"Team members sync error ({code}): {res}")

        # 8. Sync Project Applications
        apps = [dict(r) for r in conn.execute("SELECT * FROM project_applications").fetchall()]
        if apps:
            code, res = supabase_request('project_applications', method='POST', data=apps,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['applications'] = len(apps)
            else:
                report['errors'].append(f"Project applications sync error ({code}): {res}")

        # 9. Sync Invitations
        invs = [dict(r) for r in conn.execute("SELECT * FROM invitations").fetchall()]
        if invs:
            code, res = supabase_request('invitations', method='POST', data=invs,
                                         extra_headers={'Prefer': 'resolution=merge-duplicates'})
            if code in (200, 201):
                report['invitations'] = len(invs)
            else:
                report['errors'].append(f"Invitations sync error ({code}): {res}")

    finally:
        conn.close()

    success = len(report['errors']) == 0
    needs_schema = any('404' in str(err) or 'Could not find the table' in str(err) for err in report['errors'])
    if needs_schema:
        msg = "Supabase tables not initialized. Please run 'supabase_schema.sql' in the Supabase Dashboard SQL Editor (https://supabase.com/dashboard/project/ujjwwgjybmbysqkptfam/sql) to create the schema."
    elif success:
        msg = 'Sync completed successfully!'
    else:
        msg = f"Sync completed with {len(report['errors'])} error(s)."

    return {
        'success': success,
        'report': report,
        'needs_schema': needs_schema,
        'message': msg
    }


def sync_cloud_to_local_listings(db_path=None):
    """
    Safely hydrate the local SQLite database from persistent Supabase tables.
    Used on serverless platforms (e.g. Vercel /tmp) or on startup when cloud is enabled.
    """
    from app.models import get_listings_db

    if not is_cloud_enabled():
        return False, "Cloud sync is disabled."

    try:
        # 1. Fetch projects
        code, cloud_projects = supabase_request('projects', method='GET', query_params={'select': '*'}, timeout=5)
        if code != 200 or not isinstance(cloud_projects, list):
            return False, f"Could not fetch cloud projects (status {code})"

        conn = get_listings_db(db_path)
        cur = conn.cursor()

        for p in cloud_projects:
            cur.execute("""
                INSERT OR REPLACE INTO projects (
                    id, owner_id, title, description, category, objectives, technologies,
                    duration, collaboration_mode, availability, additional_requirements,
                    course_context, team_size_min, team_size_max, schedule_notes, status,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                p.get('id'), p.get('owner_id'), p.get('title'), p.get('description'),
                p.get('category'), p.get('objectives'), p.get('technologies'),
                p.get('duration'), p.get('collaboration_mode'), p.get('availability'),
                p.get('additional_requirements'), p.get('course_context'),
                p.get('team_size_min', 2), p.get('team_size_max', 4),
                p.get('schedule_notes'), p.get('status', 'published'),
                p.get('created_at'), p.get('updated_at')
            ))

        # 2. Fetch skill requirements
        req_code, cloud_reqs = supabase_request('project_skill_requirements', method='GET', query_params={'select': '*'}, timeout=5)
        if req_code == 200 and isinstance(cloud_reqs, list):
            for r in cloud_reqs:
                cur.execute("""
                    INSERT OR REPLACE INTO project_skill_requirements (
                        id, project_id, skill_id, priority, proficiency_level, weight
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    r.get('id'), r.get('project_id'), r.get('skill_id'),
                    r.get('priority', 'must-have'), r.get('proficiency_level', 'Intermediate'),
                    r.get('weight', 3.0)
                ))

        conn.commit()
        conn.close()
        return True, f"Synchronized {len(cloud_projects)} projects from Supabase."
    except Exception as e:
        return False, f"Cloud hydration warning: {str(e)}"
