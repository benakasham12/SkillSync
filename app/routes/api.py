"""
Taxonomy and utility API endpoints.
"""

from flask import Blueprint, jsonify
from app.models import query_db

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/skills')
def get_skills():
    """Returns all active skills grouped by category."""
    skills = query_db("SELECT * FROM skills WHERE active = 1 ORDER BY category, name")
    grouped = {}
    for s in skills:
        grouped.setdefault(s['category'], []).append({
            'id': s['id'],
            'name': s['name']
        })
    return jsonify(grouped)


@api_bp.route('/api/interests')
def get_interests():
    """Returns all active interests."""
    interests = query_db("SELECT * FROM interests ORDER BY category, name")
    return jsonify(interests)


@api_bp.route('/api/cloud/status')
def cloud_status():
    """Returns status and connectivity information for the Supabase cloud database."""
    from app.supabase_client import get_supabase_config, ping_supabase, is_cloud_enabled
    cfg = get_supabase_config()
    is_online, msg = ping_supabase()
    return jsonify({
        'enabled': is_cloud_enabled(),
        'configured': bool(cfg['url'] and cfg['key']),
        'cloud_url': cfg['url'],
        'connected': is_online,
        'message': msg
    })


@api_bp.route('/api/cloud/sync', methods=['POST'])
def cloud_sync():
    """Triggers synchronization of local public listings to Supabase cloud."""
    from app.supabase_client import sync_local_listings_to_cloud
    result = sync_local_listings_to_cloud()
    return jsonify(result), (200 if result.get('success') else 500)

