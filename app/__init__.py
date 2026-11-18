"""
Flask Application Factory for SkillSync.
"""

import os
from flask import Flask, session
from app.models import init_db, query_db


def create_app(db_path=None, test_config=None):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'skillsync-bmsit-cse13-secret-key-2026'
    app.config['DATABASE'] = db_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'skillsync.db')

    if test_config:
        app.config.update(test_config)

    # Initialize DB schema if not exists
    with app.app_context():
        init_db(app.config['DATABASE'])

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.profile import profile_bp
    from app.routes.projects import projects_bp
    from app.routes.invitations import invitations_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(invitations_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Global template context processor
    @app.context_processor
    def inject_user_context():
        uid = session.get('user_id')
        unread_invites_count = 0
        user_name = session.get('user_name')
        user_email = session.get('user_email')
        user_role = session.get('user_role')

        if uid:
            res = query_db("SELECT COUNT(*) as cnt FROM invitations WHERE invitee_id = ? AND status = 'pending'", (uid,), one=True)
            unread_invites_count = res['cnt'] if res else 0

            if not user_name:
                prof = query_db("SELECT display_name FROM student_profiles WHERE user_id = ?", (uid,), one=True)
                if prof and prof['display_name']:
                    user_name = prof['display_name']
                else:
                    u = query_db("SELECT email, role FROM users WHERE id = ?", (uid,), one=True)
                    if u:
                        user_email = u['email']
                        user_name = u['email'].split('@')[0]
                        user_role = u['role']

        return {
            'current_user_id': uid,
            'current_user_name': user_name or 'User',
            'current_user_email': user_email,
            'current_user_role': user_role,
            'unread_invites_count': unread_invites_count
        }

    return app
