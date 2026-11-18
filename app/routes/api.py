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
