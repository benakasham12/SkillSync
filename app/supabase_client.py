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
    key = os.environ.get('SUPABASE_KEY', '')
    rest_url = os.environ.get('SUPABASE_REST_URL', '').rstrip('/')
    if url and not rest_url:
        rest_url = f"{url}/rest/v1"

    use_cloud = os.environ.get('USE_SUPABASE', 'false').lower() in ('true', '1', 'yes')

    return {
        'url': url,
        'key': key,
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
    report = {'skills': 0, 'interests': 0, 'projects': 0, 'requirements': 0, 'errors': []}

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

    finally:
        conn.close()

    success = len(report['errors']) == 0
    return {
        'success': success,
        'report': report,
        'message': 'Sync completed successfully!' if success else f"Sync completed with {len(report['errors'])} error(s)."
    }
